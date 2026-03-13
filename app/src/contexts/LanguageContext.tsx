import { createContext, useContext, useState, type ReactNode } from 'react';

type Language = 'zh' | 'en';

interface Translations {
  // Header
  title: string;
  subtitle: string;
  // Card
  noteLink: string;
  linkPlaceholder: string;
  linkDescription: string;
  // Button
  generate: string;
  generating: string;
  // Format
  selectFormat: string;
  pdfFormat: string;
  markdownFormat: string;
  // Status
  inputUrl: string;
  parsing: string;
  downloading: string;
  success: string;
  error: string;
  // Download
  downloadPdf: string;
  downloadMarkdown: string;
  startDownload: string;
  // Features
  pasteLink: string;
  autoParse: string;
  download: string;
  // Footer
  disclaimer: string;
  // Toast
  inputError: string;
  invalidUrlError: string;
  convertError: string;
  generateSuccess: string;
}

const translations: Record<Language, Translations> = {
  zh: {
    title: '小红书笔记转PDF/Markdown',
    subtitle: '输入小红书笔记链接，一键生成PDF或Markdown文件',
    noteLink: '笔记链接',
    linkPlaceholder: '粘贴小红书笔记链接...',
    linkDescription: '支持 xhslink.com 和 xiaohongshu.com 链接',
    generate: '生成',
    generating: '处理中',
    selectFormat: '选择格式',
    pdfFormat: 'PDF 格式',
    markdownFormat: 'Markdown 格式',
    inputUrl: '请输入小红书笔记链接',
    parsing: '正在解析笔记内容...',
    downloading: '正在下载图片...',
    success: '成功生成',
    error: '转换失败',
    downloadPdf: '下载PDF文件',
    downloadMarkdown: '下载Markdown文件 (ZIP)',
    startDownload: '开始下载',
    pasteLink: '粘贴链接',
    autoParse: '自动解析',
    download: '下载',
    disclaimer: '工具仅供学习使用，请遵守相关法律法规',
    inputError: '请输入小红书笔记链接',
    invalidUrlError: '请输入有效的小红书笔记链接',
    convertError: '转换过程中出现错误',
    generateSuccess: '生成成功！',
  },
  en: {
    title: 'Xiaohongshu to PDF/Markdown',
    subtitle: 'Enter a Xiaohongshu note link to generate PDF or Markdown instantly',
    noteLink: 'Note Link',
    linkPlaceholder: 'Paste Xiaohongshu note link...',
    linkDescription: 'Supports xhslink.com and xiaohongshu.com links',
    generate: 'Generate',
    generating: 'Processing',
    selectFormat: 'Select Format',
    pdfFormat: 'PDF Format',
    markdownFormat: 'Markdown Format',
    inputUrl: 'Please enter a Xiaohongshu note link',
    parsing: 'Parsing note content...',
    downloading: 'Downloading images...',
    success: 'Successfully generated',
    error: 'Conversion failed',
    downloadPdf: 'Download PDF',
    downloadMarkdown: 'Download Markdown (ZIP)',
    startDownload: 'Starting download',
    pasteLink: 'Paste Link',
    autoParse: 'Auto Parse',
    download: 'Download',
    disclaimer: 'For learning purposes only, please comply with relevant laws',
    inputError: 'Please enter a Xiaohongshu note link',
    invalidUrlError: 'Please enter a valid Xiaohongshu note link',
    convertError: 'An error occurred during conversion',
    generateSuccess: 'Generated successfully!',
  },
};

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: Translations;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const LANGUAGE_KEY = 'xhs-pdf-language';

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem(LANGUAGE_KEY);
    return (saved as Language) || 'zh';
  });

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem(LANGUAGE_KEY, lang);
  };

  const t = translations[language];

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
