#!/usr/bin/env python3
"""
Интерактивный дашборд для анализа качества чат-бота
Использует Streamlit для создания веб-интерфейса с вкладками
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sqlite3
from datetime import datetime, timedelta
import requests
import json
import time

# Конфигурация страницы
st.set_page_config(
    page_title="Чат-бот Аналитика",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS для улучшения внешнего вида
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    """Загрузка данных из базы данных с кэшированием"""
    try:
        conn = sqlite3.connect('instance/chatbot_logs.db')
        query = """
        SELECT id, user_id, session_id, timestamp, query_text, bot_response, 
               intent, resolved, rating, response_time, channel, language
        FROM interaction_log 
        ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Преобразуем timestamp в datetime (поддерживаем разные форматы)
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce')
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame()

def get_bot_response(message):
    """Получение ответа от бота через API"""
    try:
        response = requests.post(
            'http://localhost:5000/chat',
            json={
                'message': message,
                'user_id': 'dashboard_user',
                'session_id': f'dashboard_session_{int(time.time())}',
                'channel': 'dashboard',
                'language': 'ru'
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['response'], data.get('log_id')
        else:
            return f"Ошибка API: {response.status_code}", None
    except Exception as e:
        return f"⚠️ Чат-бот API недоступен. Запустите сервер: py app.py", None

def rate_response(log_id, rating):
    """Отправка оценки ответа"""
    try:
        response = requests.post(
            'http://localhost:5000/rate',
            json={'log_id': log_id, 'rating': rating},
            timeout=10
        )
        if response.status_code == 200:
            return True
        else:
            st.error(f"Ошибка API: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.Timeout:
        st.error("Таймаут при отправке оценки")
        return False
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Чат-бот API недоступен. Запустите сервер: py app.py")
        return False
    except Exception as e:
        st.error(f"Неожиданная ошибка: {e}")
        return False

def chat_tab():
    """Вкладка для тестирования чат-бота"""
    st.markdown('<h2 class="main-header">💬 Тестирование Чат-бота</h2>', unsafe_allow_html=True)
    
    # Инициализация состояния чата
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    # Отображение истории чата
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if message["role"] == "assistant" and "log_id" in message:
                    # Кнопки оценки
                    log_id = message['log_id']
                    if log_id and log_id != "None":
                        st.write("**Оцените ответ:**")
                        cols = st.columns(5)
                        for i, col in enumerate(cols, 1):
                            with col:
                                if st.button(f"⭐{i}", key=f"rate_{log_id}_{i}_{len(st.session_state.messages)}"):
                                    with st.spinner("Сохранение оценки..."):
                                        if rate_response(log_id, i):
                                            st.success(f"✅ Оценка {i} сохранена!")
                                            # Небольшая задержка перед обновлением
                                            time.sleep(0.5)
                                            st.rerun()
                                        # Ошибка уже показана в функции rate_response
                    else:
                        st.info("⚠️ ID записи недоступен для оценки")

def dashboard_tab():
    """Вкладка с аналитикой и метриками"""
    st.markdown('<h2 class="main-header">📊 Аналитика Чат-бота</h2>', unsafe_allow_html=True)
    
    # Кнопка обновления данных
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Обновить данные", help="Обновить данные из базы"):
            st.cache_data.clear()
            st.rerun()
    
    # Загружаем данные
    df = load_data()
    
    if df.empty:
        st.warning("Нет данных для отображения. Убедитесь, что чат-бот работает и есть записи в базе данных.")
        return
    
    # Информация о данных
    latest_timestamp = df['timestamp'].max() if not df.empty else None
    if latest_timestamp:
        st.info(f"📊 Данные обновлены: {latest_timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Всего записей: {len(df)}")
    
    # Фильтры в боковой панели
    st.sidebar.header("🔍 Фильтры")
    
    # Фильтр по дате
    if not df.empty:
        min_date = df['date'].min()
        max_date = df['date'].max()
        
        date_range = st.sidebar.date_input(
            "Период",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    # Фильтр по намерениям
    intents = st.sidebar.multiselect(
        "Намерения",
        options=df['intent'].unique(),
        default=df['intent'].unique()
    )
    if intents:
        df = df[df['intent'].isin(intents)]
    
    # Фильтр по каналам
    channels = st.sidebar.multiselect(
        "Каналы",
        options=df['channel'].unique(),
        default=df['channel'].unique()
    )
    if channels:
        df = df[df['channel'].isin(channels)]
    
    # Основные KPI метрики
    st.subheader("📈 Ключевые показатели эффективности (KPI)")
    
    # Вычисляем метрики
    # Загружаем полные данные для общих метрик (без фильтров)
    full_df = load_data()
    total_interactions = len(full_df)  # Общее количество в БД
    total_rated_interactions = len(full_df[full_df['rating'].notna()])
    total_avg_rating = full_df['rating'].mean() if not full_df.empty and full_df['rating'].notna().any() else 0
    total_resolution_rate = (full_df['resolved'].sum() / len(full_df) * 100) if len(full_df) > 0 else 0
    total_avg_response_time = full_df['response_time'].mean() if not full_df.empty else 0
    total_unique_users = full_df['user_id'].nunique() if not full_df.empty else 0
    
    # Метрики для отфильтрованных данных
    filtered_interactions = len(df)
    rated_interactions = len(df[df['rating'].notna()])
    avg_rating = df['rating'].mean() if not df.empty and df['rating'].notna().any() else 0
    resolution_rate = (df['resolved'].sum() / len(df) * 100) if len(df) > 0 else 0
    avg_response_time = df['response_time'].mean() if not df.empty else 0
    unique_users = df['user_id'].nunique() if not df.empty else 0
    
    # CSAT (Customer Satisfaction) - используем полные данные
    positive_ratings = len(full_df[full_df['rating'] >= 4]) if not full_df.empty else 0
    csat_rate = (positive_ratings / total_rated_interactions * 100) if total_rated_interactions > 0 else 0
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "CSAT (Удовлетворенность)", 
            f"{total_avg_rating:.1f}/5",
            delta=f"{csat_rate:.1f}% позитивных" if csat_rate > 0 else None
        )
    
    with col2:
        st.metric(
            "Успешно решенных", 
            f"{total_resolution_rate:.1f}%",
            delta=f"{full_df['resolved'].sum()}/{total_interactions}" if total_interactions > 0 else None
        )
    
    with col3:
        st.metric(
            "Среднее время ответа", 
            f"{total_avg_response_time:.2f}с",
            delta="⚡ Быстро" if total_avg_response_time < 1.0 else "🐌 Медленно" if total_avg_response_time > 2.0 else None
        )
    
    with col4:
        st.metric(
            "Активные пользователи", 
            total_unique_users,
            delta=f"{total_interactions/total_unique_users:.1f} запросов/пользователь" if total_unique_users > 0 else None
        )
    
    with col5:
        st.metric(
            "Всего взаимодействий", 
            total_interactions,
            delta=f"{total_rated_interactions} оцененных" if total_rated_interactions > 0 else None
        )
    
    # Графики
    st.subheader("📊 Визуализация данных")
    
    # Создаем вкладки для разных типов графиков
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Временные ряды", "🎯 Намерения", "⭐ Оценки", "👥 Пользователи", "📋 Проблемные случаи"])
    
    with tab1:
        # Динамика по времени
        if not df.empty:
            # График активности по дням
            daily_activity = df.groupby('date').agg({
                'id': 'count',
                'rating': 'mean',
                'resolved': 'mean',
                'response_time': 'mean'
            }).reset_index()
            daily_activity.columns = ['date', 'interactions', 'avg_rating', 'resolution_rate', 'avg_response_time']
            
            # Создаем субплоты
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Активность по дням', 'Средний рейтинг по дням', 
                              'Процент решенных по дням', 'Среднее время ответа по дням'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                     [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # График активности
            fig.add_trace(
                go.Scatter(x=daily_activity['date'], y=daily_activity['interactions'], 
                          mode='lines+markers', name='Взаимодействия', line=dict(color='#1f77b4')),
                row=1, col=1
            )
            
            # График рейтинга
            fig.add_trace(
                go.Scatter(x=daily_activity['date'], y=daily_activity['avg_rating'], 
                          mode='lines+markers', name='Средний рейтинг', line=dict(color='#ff7f0e')),
                row=1, col=2
            )
            
            # График процента решенных
            fig.add_trace(
                go.Scatter(x=daily_activity['date'], y=daily_activity['resolution_rate']*100, 
                          mode='lines+markers', name='% Решенных', line=dict(color='#2ca02c')),
                row=2, col=1
            )
            
            # График времени ответа
            fig.add_trace(
                go.Scatter(x=daily_activity['date'], y=daily_activity['avg_response_time'], 
                          mode='lines+markers', name='Время ответа (с)', line=dict(color='#d62728')),
                row=2, col=2
            )
            
            fig.update_layout(height=600, showlegend=True, title_text="Динамика ключевых метрик по дням")
            st.plotly_chart(fig, use_container_width=True)
            
            # График активности по часам
            hourly_activity = df.groupby('hour').size().reset_index(name='count')
            
            fig_hourly = px.bar(
                hourly_activity, 
                x='hour', 
                y='count',
                title="Распределение активности по часам дня",
                labels={'hour': 'Час дня', 'count': 'Количество взаимодействий'},
                color='count',
                color_continuous_scale='Blues'
            )
            fig_hourly.update_layout(xaxis_title="Час дня", yaxis_title="Количество взаимодействий")
            st.plotly_chart(fig_hourly, use_container_width=True)
    
    with tab2:
        # Аналитика по категориям запросов
        if not df.empty:
            # Анализ по намерениям с качеством
            intent_analysis = df.groupby('intent').agg({
                'id': 'count',
                'rating': 'mean',
                'resolved': 'mean',
                'response_time': 'mean'
            }).reset_index()
            intent_analysis.columns = ['Намерение', 'Количество', 'Средний_рейтинг', 'Процент_решенных', 'Среднее_время']
            
            # Заполняем NaN значения и приводим к числовому типу
            intent_analysis['Средний_рейтинг'] = pd.to_numeric(intent_analysis['Средний_рейтинг'], errors='coerce').fillna(0)
            intent_analysis['Процент_решенных'] = pd.to_numeric(intent_analysis['Процент_решенных'], errors='coerce').fillna(0) * 100
            intent_analysis['Среднее_время'] = pd.to_numeric(intent_analysis['Среднее_время'], errors='coerce').fillna(0)
            
            # Круговая диаграмма распределения
            fig_pie = px.pie(
                intent_analysis,
                values='Количество',
                names='Намерение',
                title="Распределение запросов по намерениям",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Комбинированная диаграмма: количество и качество
            fig_combined = make_subplots(
                rows=1, cols=2,
                subplot_titles=('Количество запросов по намерениям', 'Качество ответов по намерениям'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # Количество запросов
            fig_combined.add_trace(
                go.Bar(x=intent_analysis['Намерение'], y=intent_analysis['Количество'], 
                      name='Количество', marker_color='#1f77b4'),
                row=1, col=1
            )
            
            # Средний рейтинг
            fig_combined.add_trace(
                go.Bar(x=intent_analysis['Намерение'], y=intent_analysis['Средний_рейтинг'], 
                      name='Средний рейтинг', marker_color='#ff7f0e'),
                row=1, col=2
            )
            
            fig_combined.update_layout(height=400, showlegend=True, 
                                     title_text="Анализ намерений: количество и качество")
            fig_combined.update_xaxes(tickangle=45)
            st.plotly_chart(fig_combined, use_container_width=True)
            
            # Детальная таблица по намерениям
            st.subheader("📊 Детальный анализ по намерениям")
            display_intent = intent_analysis.copy()
            
            # Безопасное округление с проверкой типов данных
            if pd.api.types.is_numeric_dtype(display_intent['Средний_рейтинг']):
                display_intent['Средний_рейтинг'] = display_intent['Средний_рейтинг'].round(2)
            else:
                display_intent['Средний_рейтинг'] = display_intent['Средний_рейтинг'].astype(str)
                
            if pd.api.types.is_numeric_dtype(display_intent['Процент_решенных']):
                display_intent['Процент_решенных'] = display_intent['Процент_решенных'].round(1)
            else:
                display_intent['Процент_решенных'] = display_intent['Процент_решенных'].astype(str)
                
            if pd.api.types.is_numeric_dtype(display_intent['Среднее_время']):
                display_intent['Среднее_время'] = display_intent['Среднее_время'].round(3)
            else:
                display_intent['Среднее_время'] = display_intent['Среднее_время'].astype(str)
            
            st.dataframe(
                display_intent,
                use_container_width=True,
                column_config={
                    "Намерение": "Намерение",
                    "Количество": "Запросов",
                    "Средний_рейтинг": "Ср. рейтинг",
                    "Процент_решенных": "% Решенных",
                    "Среднее_время": "Время (с)"
                }
            )
    
    with tab3:
        # Анализ оценок
        if not df.empty and df['rating'].notna().any():
            rating_counts = df['rating'].value_counts().sort_index().reset_index()
            rating_counts.columns = ['Оценка', 'Количество']
            
            fig = px.bar(
                rating_counts,
                x='Оценка',
                y='Количество',
                title="Распределение оценок",
                color='Оценка',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Временной ряд оценок
            df_with_ratings = df[df['rating'].notna()].copy()
            if not df_with_ratings.empty:
                df_with_ratings['date'] = df_with_ratings['timestamp'].dt.date
                daily_ratings = df_with_ratings.groupby('date')['rating'].mean().reset_index()
                
                fig2 = px.line(
                    daily_ratings,
                    x='date',
                    y='rating',
                    title="Средняя оценка по дням",
                    labels={'date': 'Дата', 'rating': 'Средняя оценка'}
                )
                fig2.update_layout(yaxis=dict(range=[1, 5]))
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Нет данных об оценках для отображения")
    
    with tab4:
        # Аналитика по пользователям
        if not df.empty:
            # Анализ активности пользователей
            user_analysis = df.groupby('user_id').agg({
                'id': 'count',
                'rating': 'mean',
                'resolved': 'mean',
                'response_time': 'mean'
            }).reset_index()
            user_analysis.columns = ['Пользователь', 'Запросов', 'Средний_рейтинг', 'Процент_решенных', 'Среднее_время']
            
            # Заполняем NaN значения и приводим к числовому типу
            user_analysis['Средний_рейтинг'] = pd.to_numeric(user_analysis['Средний_рейтинг'], errors='coerce').fillna(0)
            user_analysis['Процент_решенных'] = pd.to_numeric(user_analysis['Процент_решенных'], errors='coerce').fillna(0) * 100
            user_analysis['Среднее_время'] = pd.to_numeric(user_analysis['Среднее_время'], errors='coerce').fillna(0)
            
            # Распределение по количеству запросов
            fig_requests = px.histogram(
                user_analysis,
                x='Запросов',
                title="Распределение пользователей по количеству запросов",
                labels={'Запросов': 'Количество запросов', 'count': 'Количество пользователей'},
                nbins=20
            )
            st.plotly_chart(fig_requests, use_container_width=True)
            
            # Топ пользователей
            st.subheader("👑 Топ-10 активных пользователей")
            top_users = user_analysis.nlargest(10, 'Запросов')
            
            # Безопасное округление с проверкой типов данных
            if pd.api.types.is_numeric_dtype(top_users['Средний_рейтинг']):
                top_users['Средний_рейтинг'] = top_users['Средний_рейтинг'].round(2)
            else:
                top_users['Средний_рейтинг'] = top_users['Средний_рейтинг'].astype(str)
                
            if pd.api.types.is_numeric_dtype(top_users['Процент_решенных']):
                top_users['Процент_решенных'] = top_users['Процент_решенных'].round(1)
            else:
                top_users['Процент_решенных'] = top_users['Процент_решенных'].astype(str)
            
            st.dataframe(
                top_users,
                use_container_width=True,
                column_config={
                    "Пользователь": "Пользователь",
                    "Запросов": "Запросов",
                    "Средний_рейтинг": "Ср. рейтинг",
                    "Процент_решенных": "% Решенных",
                    "Среднее_время": "Время (с)"
                }
            )
            
            # Корреляция между количеством запросов и удовлетворенностью
            fig_corr = px.scatter(
                user_analysis,
                x='Запросов',
                y='Средний_рейтинг',
                title="Корреляция: количество запросов vs удовлетворенность",
                labels={'Запросов': 'Количество запросов', 'Средний_рейтинг': 'Средний рейтинг'},
                color='Процент_решенных',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_corr, use_container_width=True)
    
    with tab5:
        # Проблемные случаи
        if not df.empty:
            # Негативные оценки
            negative_cases = df[df['rating'] <= 2].copy() if df['rating'].notna().any() else pd.DataFrame()
            
            # Нераспознанные запросы
            unknown_cases = df[df['intent'] == 'unknown'].copy()
            
            # Нерешенные запросы
            unresolved_cases = df[df['resolved'] == False].copy()
            
            st.subheader("🚨 Проблемные случаи")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Негативные оценки (≤2)", len(negative_cases))
            with col2:
                st.metric("Нераспознанные запросы", len(unknown_cases))
            with col3:
                st.metric("Нерешенные запросы", len(unresolved_cases))
            
            # Таблица негативных оценок
            if not negative_cases.empty:
                st.subheader("👎 Случаи с негативными оценками")
                display_negative = negative_cases[['timestamp', 'user_id', 'query_text', 'bot_response', 'rating', 'intent']].copy()
                display_negative['timestamp'] = display_negative['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(display_negative, use_container_width=True)
            
            # Таблица нераспознанных запросов
            if not unknown_cases.empty:
                st.subheader("❓ Нераспознанные запросы")
                display_unknown = unknown_cases[['timestamp', 'user_id', 'query_text', 'bot_response', 'rating']].copy()
                display_unknown['timestamp'] = display_unknown['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(display_unknown, use_container_width=True)
            
            # Управление данными
            st.subheader("📋 Управление данными")
            
            # Экспорт в CSV
            if st.button("📥 Экспорт в CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Скачать CSV",
                    data=csv,
                    file_name=f"chatbot_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Просмотр всех данных
            st.subheader("📊 Все данные")
            
            # Показываем последние 50 записей
            display_df_all = df.head(50)[['timestamp', 'user_id', 'query_text', 'bot_response', 'intent', 'rating', 'resolved']].copy()
            display_df_all['timestamp'] = display_df_all['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            st.dataframe(
                display_df_all,
                use_container_width=True,
                column_config={
                    "timestamp": "Время",
                    "user_id": "Пользователь",
                    "query_text": "Запрос",
                    "bot_response": "Ответ",
                    "intent": "Намерение",
                    "rating": "Оценка",
                    "resolved": "Решен"
                }
            )

def main():
    """Основная функция приложения"""
    # Заголовок
    st.markdown('<h1 class="main-header">🤖 Аналитический Дашборд Чат-бота</h1>', unsafe_allow_html=True)
    
    # Проверка подключения к API
    try:
        response = requests.get('http://localhost:5000/status', timeout=2)
        if response.status_code == 200:
            st.success("✅ Чат-бот API подключен")
        else:
            st.warning("⚠️ Чат-бот API недоступен")
    except:
        st.info("ℹ️ Чат-бот API не запущен. Для тестирования запустите: py app.py")
    
    # Создаем вкладки
    tab1, tab2 = st.tabs(["💬 Тестирование", "📊 Аналитика"])
    
    with tab1:
        chat_tab()
    
    with tab2:
        dashboard_tab()
    
    # Поле ввода для чата (вне вкладок)
    if prompt := st.chat_input("Введите ваше сообщение..."):
        # Инициализация состояния чата если нужно
        if 'messages' not in st.session_state:
            st.session_state.messages = []
            
        # Добавляем сообщение пользователя
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Получаем ответ от бота
        with st.spinner("Бот печатает..."):
            response, log_id = get_bot_response(prompt)
        
        # Добавляем ответ бота
        bot_message = {"role": "assistant", "content": response}
        if log_id:
            bot_message["log_id"] = log_id
        st.session_state.messages.append(bot_message)
        
        # Обновляем интерфейс
        st.rerun()

if __name__ == "__main__":
    main()

