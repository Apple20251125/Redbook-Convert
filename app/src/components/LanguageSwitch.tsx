import { Globe } from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';

export function LanguageSwitch() {
  const { language, setLanguage } = useLanguage();

  return (
    <div className="absolute top-4 right-4 flex items-center gap-2">
      <Globe className="w-4 h-4 text-gray-500" />
      <button
        onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')}
        className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
      >
        {language === 'zh' ? 'EN' : '中'}
      </button>
    </div>
  );
}
