import { useEffect, useState } from 'react';
import { VoiceChatV2 } from './components/VoiceChatV2';
import './App.css';

// Конфигурация
const API_URL = import.meta.env.VITE_API_URL || 'ws://localhost:8000';
const WS_URL = `${API_URL.replace('http', 'ws')}/api/v1/voice/chat`;

function App() {
  const [userId, setUserId] = useState<number>(1); // Default user ID
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Проверяем Telegram WebApp
    const tg = (window as any).Telegram?.WebApp;

    if (tg) {
      // Инициализируем Telegram WebApp
      tg.ready();
      tg.expand(); // Разворачиваем на весь экран

      // Получаем user_id из Telegram
      const tgUserId = tg.initDataUnsafe?.user?.id;
      if (tgUserId) {
        setUserId(tgUserId);
        console.log('Telegram user ID:', tgUserId);
      }

      // Настраиваем тему
      document.documentElement.style.setProperty(
        '--tg-theme-bg-color',
        tg.themeParams?.bg_color || '#ffffff'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-text-color',
        tg.themeParams?.text_color || '#000000'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-hint-color',
        tg.themeParams?.hint_color || '#999999'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-button-color',
        tg.themeParams?.button_color || '#667eea'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-button-text-color',
        tg.themeParams?.button_text_color || '#ffffff'
      );
      document.documentElement.style.setProperty(
        '--tg-theme-secondary-bg-color',
        tg.themeParams?.secondary_bg_color || '#f0f0f0'
      );

      console.log('Telegram WebApp initialized');
    } else {
      console.log('Running outside Telegram');
    }

    setIsReady(true);
  }, []);

  if (!isReady) {
    return (
      <div className="loading">
        <div className="loading-spinner"></div>
        <p>Loading...</p>
      </div>
    );
  }

  return <VoiceChatV2 userId={userId} wsUrl={WS_URL} />;
}

export default App;
