#!/usr/bin/env python3
"""
Скрипт для синхронизации данных между CSV файлом и базой данных SQLite
Обеспечивает двустороннюю синхронизацию с мониторингом изменений
"""

import pandas as pd
import sqlite3
import os
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CSVDBSync:
    """Класс для синхронизации данных между CSV и базой данных"""
    
    def __init__(self, csv_path: str = 'chatbot_logs.csv', db_path: str = 'instance/chatbot_logs.db'):
        self.csv_path = csv_path
        self.db_path = db_path
        self.last_csv_hash = None
        self.last_db_count = 0
        
        # Создаем директорию для БД если не существует
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Инициализируем базу данных
        self._init_database()
        
    def _init_database(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Создаем таблицу если не существует
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS interaction_log (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    query_text TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    intent TEXT,
                    resolved INTEGER DEFAULT 1,
                    rating INTEGER,
                    response_time REAL,
                    channel TEXT DEFAULT 'web',
                    language TEXT DEFAULT 'ru'
                )
            ''')
            
            # Создаем индексы для оптимизации
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON interaction_log(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON interaction_log(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON interaction_log(timestamp)')
            
            conn.commit()
            conn.close()
            logger.info("База данных инициализирована")
            
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def _get_csv_hash(self) -> str:
        """Получение хеша CSV файла для отслеживания изменений"""
        try:
            if not os.path.exists(self.csv_path):
                return ""
            
            with open(self.csv_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.error(f"Ошибка получения хеша CSV: {e}")
            return ""
    
    def _get_db_count(self) -> int:
        """Получение количества записей в базе данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM interaction_log')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Ошибка получения количества записей из БД: {e}")
            return 0
    
    def csv_to_db(self) -> bool:
        """Синхронизация данных из CSV в базу данных"""
        try:
            if not os.path.exists(self.csv_path):
                logger.warning(f"CSV файл {self.csv_path} не найден")
                return False
            
            # Читаем CSV
            try:
                df = pd.read_csv(self.csv_path)
            except pd.errors.EmptyDataError:
                # Если файл содержит только заголовки или пуст
                df = pd.DataFrame()
            
            # Подключаемся к базе данных
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if df.empty:
                logger.info("CSV файл пуст - удаляем все записи из БД")
                # Если CSV пуст, удаляем все записи из БД
                cursor.execute('DELETE FROM interaction_log')
                conn.commit()
                conn.close()
                logger.info("Все записи удалены из БД")
                return True
            
            # Получаем существующие ID из БД
            cursor.execute('SELECT id FROM interaction_log')
            existing_ids = set(row[0] for row in cursor.fetchall())
            
            # Получаем ID из CSV
            csv_ids = set(df['id'].tolist()) if not df.empty and 'id' in df.columns else set()
            
            # Удаляем записи из БД, которых нет в CSV
            ids_to_delete = existing_ids - csv_ids
            if ids_to_delete:
                placeholders = ','.join('?' * len(ids_to_delete))
                cursor.execute(f'DELETE FROM interaction_log WHERE id IN ({placeholders})', list(ids_to_delete))
                logger.info(f"Удалено {len(ids_to_delete)} записей из БД")
            
            # Добавляем или обновляем записи из CSV
            for _, row in df.iterrows():
                # Подготавливаем данные
                data = {
                    'id': row.get('id'),
                    'user_id': row.get('user_id', ''),
                    'session_id': row.get('session_id', ''),
                    'timestamp': row.get('timestamp', ''),
                    'query_text': row.get('query_text', ''),
                    'bot_response': row.get('bot_response', ''),
                    'intent': row.get('intent'),
                    'resolved': int(row.get('resolved', 1)) if pd.notna(row.get('resolved')) else 1,
                    'rating': int(row.get('rating')) if pd.notna(row.get('rating')) else None,
                    'response_time': float(row.get('response_time')) if pd.notna(row.get('response_time')) else None,
                    'channel': row.get('channel', 'web'),
                    'language': row.get('language', 'ru')
                }
                
                # Проверяем, существует ли запись
                cursor.execute('SELECT id FROM interaction_log WHERE id = ?', (data['id'],))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Обновляем существующую запись
                    cursor.execute('''
                        UPDATE interaction_log SET
                            user_id = ?, session_id = ?, timestamp = ?, query_text = ?,
                            bot_response = ?, intent = ?, resolved = ?, rating = ?,
                            response_time = ?, channel = ?, language = ?
                        WHERE id = ?
                    ''', (
                        data['user_id'], data['session_id'], data['timestamp'],
                        data['query_text'], data['bot_response'], data['intent'],
                        data['resolved'], data['rating'], data['response_time'],
                        data['channel'], data['language'], data['id']
                    ))
                else:
                    # Вставляем новую запись
                    cursor.execute('''
                        INSERT INTO interaction_log (
                            id, user_id, session_id, timestamp, query_text,
                            bot_response, intent, resolved, rating, response_time,
                            channel, language
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['id'], data['user_id'], data['session_id'], data['timestamp'],
                        data['query_text'], data['bot_response'], data['intent'],
                        data['resolved'], data['rating'], data['response_time'],
                        data['channel'], data['language']
                    ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Синхронизация CSV -> БД завершена. Обработано {len(df)} записей")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации CSV -> БД: {e}")
            return False
    
    def db_to_csv(self) -> bool:
        """Экспорт данных из базы данных в CSV"""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Читаем все данные из БД
            df = pd.read_sql_query('''
                SELECT id, user_id, session_id, timestamp, query_text,
                       bot_response, intent, resolved, rating, response_time,
                       channel, language
                FROM interaction_log
                ORDER BY id
            ''', conn)
            
            conn.close()
            
            # Сохраняем в CSV
            df.to_csv(self.csv_path, index=False)
            
            logger.info(f"Экспорт БД -> CSV завершен. Экспортировано {len(df)} записей")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка экспорта БД -> CSV: {e}")
            return False
    
    def delete_from_csv(self, record_ids: List[int]) -> bool:
        """Удаление записей из CSV файла"""
        try:
            if not os.path.exists(self.csv_path):
                logger.warning(f"CSV файл {self.csv_path} не найден")
                return False
            
            # Читаем CSV
            df = pd.read_csv(self.csv_path)
            
            if df.empty:
                logger.info("CSV файл пуст")
                return True
            
            # Удаляем записи
            initial_count = len(df)
            df = df[~df['id'].isin(record_ids)]
            deleted_count = initial_count - len(df)
            
            # Сохраняем обновленный CSV
            df.to_csv(self.csv_path, index=False)
            
            logger.info(f"Удалено {deleted_count} записей из CSV")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления из CSV: {e}")
            return False
    
    def delete_from_db(self, record_ids: List[int]) -> bool:
        """Удаление записей из базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if record_ids:
                placeholders = ','.join('?' * len(record_ids))
                cursor.execute(f'DELETE FROM interaction_log WHERE id IN ({placeholders})', record_ids)
                deleted_count = cursor.rowcount
            else:
                deleted_count = 0
            
            conn.commit()
            conn.close()
            
            logger.info(f"Удалено {deleted_count} записей из БД")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления из БД: {e}")
            return False
    
    def sync_both_ways(self) -> bool:
        """Двусторонняя синхронизация"""
        try:
            # Сначала синхронизируем CSV -> БД
            csv_success = self.csv_to_db()
            
            # Затем экспортируем БД -> CSV (для обеспечения консистентности)
            db_success = self.db_to_csv()
            
            return csv_success and db_success
            
        except Exception as e:
            logger.error(f"Ошибка двусторонней синхронизации: {e}")
            return False
    
    def monitor_changes(self, interval: int = 5):
        """Мониторинг изменений в CSV файле"""
        logger.info(f"Запуск мониторинга изменений (интервал: {interval} сек)")
        
        while True:
            try:
                current_csv_hash = self._get_csv_hash()
                current_db_count = self._get_db_count()
                
                # Проверяем изменения в CSV
                if current_csv_hash != self.last_csv_hash:
                    logger.info("Обнаружены изменения в CSV файле")
                    if self.csv_to_db():
                        self.last_csv_hash = current_csv_hash
                        logger.info("Синхронизация CSV -> БД выполнена")
                    else:
                        logger.error("Ошибка синхронизации CSV -> БД")
                
                # Проверяем изменения в БД
                if current_db_count != self.last_db_count:
                    logger.info("Обнаружены изменения в базе данных")
                    self.last_db_count = current_db_count
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Мониторинг остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Ошибка мониторинга: {e}")
                time.sleep(interval)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики синхронизации"""
        try:
            csv_exists = os.path.exists(self.csv_path)
            csv_count = 0
            if csv_exists:
                df = pd.read_csv(self.csv_path)
                csv_count = len(df)
            
            db_count = self._get_db_count()
            
            return {
                'csv_exists': csv_exists,
                'csv_records': csv_count,
                'db_records': db_count,
                'sync_status': 'OK' if csv_count == db_count else 'OUT_OF_SYNC',
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {
                'csv_exists': False,
                'csv_records': 0,
                'db_records': 0,
                'sync_status': 'ERROR',
                'last_check': datetime.now().isoformat(),
                'error': str(e)
            }

def main():
    """Основная функция для тестирования и демонстрации"""
    sync = CSVDBSync()
    
    print("=== Синхронизация CSV и Базы Данных ===")
    print()
    
    # Показываем текущую статистику
    stats = sync.get_stats()
    print("Текущая статистика:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()
    
    # Выполняем синхронизацию
    print("Выполняем синхронизацию...")
    if sync.sync_both_ways():
        print("✅ Синхронизация завершена успешно")
    else:
        print("❌ Ошибка синхронизации")
    
    # Показываем обновленную статистику
    stats = sync.get_stats()
    print("\nОбновленная статистика:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    main()
