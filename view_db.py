#!/usr/bin/env python3
"""
Просмотр и редактирование базы данных в удобном формате
"""

import sqlite3
import pandas as pd
from datetime import datetime

def show_all_records():
    """Показать все записи в удобном формате"""
    try:
        conn = sqlite3.connect('instance/chatbot_logs.db')
        
        # Читаем все данные
        df = pd.read_sql_query('''
            SELECT id, user_id, session_id, timestamp, query_text, 
                   bot_response, intent, resolved, rating, response_time, 
                   channel, language
            FROM interaction_log 
            ORDER BY id
        ''', conn)
        
        conn.close()
        
        if df.empty:
            print("📋 База данных пуста")
            return df
        
        print("📋 Все записи в базе данных:")
        print("=" * 120)
        print(f"{'ID':<3} | {'Пользователь':<12} | {'Время':<20} | {'Запрос':<30} | {'Ответ':<30} | {'Рейтинг':<7}")
        print("-" * 120)
        
        for _, row in df.iterrows():
            query_short = row['query_text'][:28] + "..." if len(row['query_text']) > 30 else row['query_text']
            response_short = row['bot_response'][:28] + "..." if len(row['bot_response']) > 30 else row['bot_response']
            rating_str = str(row['rating']) if pd.notna(row['rating']) else "Нет"
            
            print(f"{row['id']:<3} | {row['user_id']:<12} | {row['timestamp']:<20} | {query_short:<30} | {response_short:<30} | {rating_str:<7}")
        
        print("=" * 120)
        print(f"Всего записей: {len(df)}")
        
        return df
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return pd.DataFrame()

def delete_record_by_id(record_id):
    """Удалить запись по ID"""
    try:
        conn = sqlite3.connect('instance/chatbot_logs.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли запись
        cursor.execute('SELECT id FROM interaction_log WHERE id = ?', (record_id,))
        if not cursor.fetchone():
            print(f"❌ Запись с ID {record_id} не найдена")
            conn.close()
            return False
        
        # Удаляем запись
        cursor.execute('DELETE FROM interaction_log WHERE id = ?', (record_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Запись с ID {record_id} удалена")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        return False

def delete_records_by_ids(record_ids):
    """Удалить несколько записей по ID"""
    try:
        conn = sqlite3.connect('instance/chatbot_logs.db')
        cursor = conn.cursor()
        
        # Удаляем записи
        placeholders = ','.join('?' * len(record_ids))
        cursor.execute(f'DELETE FROM interaction_log WHERE id IN ({placeholders})', record_ids)
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ Удалено {deleted_count} записей")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        return False

def delete_all_records():
    """Удалить все записи"""
    try:
        conn = sqlite3.connect('instance/chatbot_logs.db')
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM interaction_log')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"✅ Удалено {deleted_count} записей")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка удаления: {e}")
        return False

def interactive_mode():
    """Интерактивный режим"""
    print("🗄️ Редактор базы данных")
    print("=" * 40)
    
    while True:
        print("\nДоступные команды:")
        print("1. show - показать все записи")
        print("2. delete <ID> - удалить запись по ID")
        print("3. delete_many <ID1,ID2,ID3> - удалить несколько записей")
        print("4. delete_all - удалить все записи")
        print("5. quit - выйти")
        
        command = input("\nВведите команду: ").strip().lower()
        
        if command == "quit" or command == "q":
            print("👋 До свидания!")
            break
        elif command == "show":
            show_all_records()
        elif command.startswith("delete "):
            try:
                record_id = int(command.split()[1])
                delete_record_by_id(record_id)
            except (ValueError, IndexError):
                print("❌ Неверный формат. Используйте: delete <ID>")
        elif command.startswith("delete_many "):
            try:
                ids_str = command.split()[1]
                record_ids = [int(x.strip()) for x in ids_str.split(',')]
                delete_records_by_ids(record_ids)
            except (ValueError, IndexError):
                print("❌ Неверный формат. Используйте: delete_many <ID1,ID2,ID3>")
        elif command == "delete_all":
            confirm = input("⚠️ Вы уверены, что хотите удалить ВСЕ записи? (yes/no): ")
            if confirm.lower() in ['yes', 'y', 'да']:
                delete_all_records()
            else:
                print("❌ Операция отменена")
        else:
            print("❌ Неизвестная команда")

def main():
    """Основная функция"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "show":
            show_all_records()
        elif command == "delete" and len(sys.argv) > 2:
            try:
                record_id = int(sys.argv[2])
                delete_record_by_id(record_id)
            except ValueError:
                print("❌ ID должен быть числом")
        elif command == "delete_all":
            confirm = input("⚠️ Вы уверены, что хотите удалить ВСЕ записи? (yes/no): ")
            if confirm.lower() in ['yes', 'y', 'да']:
                delete_all_records()
            else:
                print("❌ Операция отменена")
        else:
            print("❌ Неизвестная команда")
    else:
        # Интерактивный режим
        interactive_mode()

if __name__ == "__main__":
    main()
