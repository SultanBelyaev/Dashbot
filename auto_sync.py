#!/usr/bin/env python3
"""
Простой скрипт для автоматической синхронизации CSV → БД
Отслеживает изменения в CSV файле и автоматически обновляет базу данных
"""

import time
import os
import hashlib
import logging
from sync_csv_db import CSVDBSync

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoSync:
    """Класс для автоматической синхронизации CSV → БД"""
    
    def __init__(self, csv_path='chatbot_logs.csv', db_path='instance/chatbot_logs.db', interval=2):
        self.csv_path = csv_path
        self.db_path = db_path
        self.interval = interval
        self.sync = CSVDBSync(csv_path, db_path)
        self.last_hash = None
        self.running = True
        
    def get_file_hash(self):
        """Получение хеша CSV файла"""
        try:
            if not os.path.exists(self.csv_path):
                return None
            
            with open(self.csv_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.error(f"Ошибка получения хеша файла: {e}")
            return None
    
    def sync_csv_to_db(self):
        """Синхронизация только CSV → БД (без обратного экспорта)"""
        try:
            if not os.path.exists(self.csv_path):
                logger.warning(f"CSV файл {self.csv_path} не найден")
                return False
            
            # Читаем CSV
            import pandas as pd
            try:
                df = pd.read_csv(self.csv_path)
            except pd.errors.EmptyDataError:
                df = pd.DataFrame()
            
            # Подключаемся к базе данных
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if df.empty:
                logger.info("CSV файл пуст - удаляем все записи из БД")
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
            
            logger.info(f"Синхронизация CSV → БД завершена. Обработано {len(df)} записей")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации CSV → БД: {e}")
            return False
    
    def start_monitoring(self):
        """Запуск мониторинга изменений"""
        logger.info(f"Запуск автоматической синхронизации CSV → БД")
        logger.info(f"CSV файл: {self.csv_path}")
        logger.info(f"База данных: {self.db_path}")
        logger.info(f"Интервал проверки: {self.interval} секунд")
        logger.info("Нажмите Ctrl+C для остановки")
        
        # Получаем начальный хеш
        self.last_hash = self.get_file_hash()
        
        try:
            while self.running:
                current_hash = self.get_file_hash()
                
                # Проверяем изменения в CSV файле
                if current_hash != self.last_hash:
                    logger.info("Обнаружены изменения в CSV файле")
                    
                    if self.sync_csv_to_db():
                        self.last_hash = current_hash
                        logger.info("Синхронизация выполнена успешно")
                    else:
                        logger.error("Ошибка синхронизации")
                
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            logger.info("Мониторинг остановлен пользователем")
        except Exception as e:
            logger.error(f"Ошибка мониторинга: {e}")
        finally:
            logger.info("Автоматическая синхронизация завершена")

def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Автоматическая синхронизация CSV → БД')
    parser.add_argument('--csv', default='chatbot_logs.csv', help='Путь к CSV файлу')
    parser.add_argument('--db', default='instance/chatbot_logs.db', help='Путь к базе данных')
    parser.add_argument('--interval', type=int, default=2, help='Интервал проверки в секундах')
    parser.add_argument('--once', action='store_true', help='Выполнить синхронизацию один раз и выйти')
    
    args = parser.parse_args()
    
    auto_sync = AutoSync(args.csv, args.db, args.interval)
    
    if args.once:
        # Выполняем синхронизацию один раз
        logger.info("Выполнение однократной синхронизации CSV → БД...")
        if auto_sync.sync_csv_to_db():
            logger.info("Синхронизация выполнена успешно")
        else:
            logger.error("Ошибка синхронизации")
    else:
        # Запускаем мониторинг
        auto_sync.start_monitoring()

if __name__ == "__main__":
    main()

