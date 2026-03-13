import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Download, Link2, Loader2, FileImage, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';
import { LanguageSwitch } from '@/components/LanguageSwitch';

interface ConversionStatus {
  status: 'idle' | 'parsing' | 'downloading' | 'generating' | 'completed' | 'error';
  message: string;
  progress: number;
  pdfUrl?: string;
  filename?: string;
}

// API基础URL - 根据环境配置
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// 从文本中提取小红书链接
const extractXhsUrl = (text: string): string => {
  // 匹配 http/https 开头的小红书链接
  const urlRegex = /(https?:\/\/[^\s]+xiaohongshu\.com[^\s]*)|(https?:\/\/[^\s]+xhslink\.com[^\s]*)/i;
  const match = text.match(urlRegex);
  if (match && match[0]) {
    // 移除可能包含的尾部标点符号
    return match[0].replace(/[。，！！？?、,，]+$/, '');
  }
  return text.trim();
};

export default function App() {
  const [url, setUrl] = useState('');
  const [format, setFormat] = useState<'pdf' | 'markdown'>('pdf');
  const [conversion, setConversion] = useState<ConversionStatus>({
    status: 'idle',
    message: '请输入小红书笔记链接',
    progress: 0,
  });

  const handleSubmit = async () => {
    if (!url.trim()) {
      toast.error('请输入小红书笔记链接');
      return;
    }

    // 从输入中提取实际的URL
    const extractedUrl = extractXhsUrl(url);

    // 验证小红书链接
    const xhsPatterns = [
      /xhslink\.com/,
      /xiaohongshu\.com/,
    ];

    const isValidXhsUrl = xhsPatterns.some(pattern => pattern.test(extractedUrl));
    if (!isValidXhsUrl) {
      toast.error('请输入有效的小红书笔记链接');
      return;
    }

    // 更新输入框显示提取的URL
    if (extractedUrl !== url) {
      setUrl(extractedUrl);
    }

    setConversion({
      status: 'parsing',
      message: '正在解析笔记内容...',
      progress: 10,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/api/convert`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: extractedUrl, format, originalText: url }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '转换失败');
      }

      const data = await response.json();

      if (data.success) {
        // 构建完整的下载URL
        const fullDownloadUrl = data.downloadUrl.startsWith('http')
          ? data.downloadUrl
          : `${API_BASE_URL}${data.downloadUrl}`;

        setConversion({
          status: 'completed',
          message: `成功生成${format === 'pdf' ? 'PDF' : 'Markdown'}！共 ${data.imageCount} 张图片`,
          progress: 100,
          pdfUrl: fullDownloadUrl,
          filename: data.filename,
        });
        toast.success(`${format === 'pdf' ? 'PDF' : 'Markdown'}生成成功！`);
      } else {
        throw new Error(data.message || '转换失败');
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '转换过程中出现错误';
      setConversion({
        status: 'error',
        message,
        progress: 0,
      });
      toast.error(message);
    }
  };

  const handleDownload = () => {
    if (conversion.pdfUrl) {
      const link = document.createElement('a');
      link.href = conversion.pdfUrl;
      link.download = conversion.filename || '小红书笔记.pdf';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success('开始下载PDF文件');
    }
  };

  const getStatusIcon = () => {
    switch (conversion.status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <FileImage className="w-5 h-5 text-red-500" />;
      case 'idle':
        return <Link2 className="w-5 h-5 text-gray-400" />;
      default:
        return <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 via-white to-red-50 flex items-center justify-center p-4">
      <LanguageSwitch />
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-red-500 to-pink-500 rounded-2xl mb-4 shadow-lg">
            <FileImage className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            小红书笔记转PDF/Markdown
          </h1>
          <p className="text-gray-600">
            输入小红书笔记链接，一键生成PDF或Markdown文件
          </p>
        </div>

        {/* Main Card */}
        <Card className="shadow-xl border-0">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">笔记链接</CardTitle>
            <CardDescription>
              支持 xhslink.com 和 xiaohongshu.com 链接
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Input Area */}
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="粘贴小红书笔记链接..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="pl-10 h-12"
                  disabled={conversion.status === 'parsing' || conversion.status === 'downloading' || conversion.status === 'generating'}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                />
              </div>
              <Button
                onClick={handleSubmit}
                disabled={conversion.status === 'parsing' || conversion.status === 'downloading' || conversion.status === 'generating' || !url.trim()}
                className="h-12 px-6 bg-gradient-to-r from-red-500 to-pink-500 hover:from-red-600 hover:to-pink-600"
              >
                {conversion.status === 'idle' || conversion.status === 'error' || conversion.status === 'completed' ? (
                  <>
                    <FileImage className="w-4 h-4 mr-2" />
                    生成{format === 'pdf' ? 'PDF' : 'Markdown'}
                  </>
                ) : (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    处理中
                  </>
                )}
              </Button>
            </div>

            {/* Format Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700">选择格式</label>
              <RadioGroup value={format} onValueChange={(value) => setFormat(value as 'pdf' | 'markdown')}>
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="pdf" id="pdf" />
                    <label htmlFor="pdf" className="text-sm">PDF 格式</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="markdown" id="markdown" />
                    <label htmlFor="markdown" className="text-sm">Markdown 格式</label>
                  </div>
                </div>
              </RadioGroup>
            </div>

            {/* Progress Area */}
            {(conversion.status !== 'idle' || conversion.message) && (
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg">
                  {getStatusIcon()}
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-700">
                      {conversion.message}
                    </p>
                  </div>
                </div>
                
                {conversion.status !== 'idle' && conversion.status !== 'completed' && conversion.status !== 'error' && (
                  <Progress value={conversion.progress} className="h-2" />
                )}
              </div>
            )}

            {/* Download Button */}
            {conversion.status === 'completed' && conversion.pdfUrl && (
              <Button
                onClick={handleDownload}
                className="w-full h-12 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
              >
                <Download className="w-4 h-4 mr-2" />
                {format === 'pdf' ? '下载PDF文件' : '下载Markdown文件 (ZIP)'}
              </Button>
            )}

            {/* Error Message */}
            {conversion.status === 'error' && (
              <Alert variant="destructive">
                <AlertDescription>{conversion.message}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Features */}
        <div className="grid grid-cols-3 gap-4 mt-8">
          <div className="text-center">
            <div className="w-12 h-12 bg-white rounded-xl shadow-sm flex items-center justify-center mx-auto mb-2">
              <Link2 className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-sm text-gray-600">粘贴链接</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-white rounded-xl shadow-sm flex items-center justify-center mx-auto mb-2">
              <Loader2 className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-sm text-gray-600">自动解析</p>
          </div>
          <div className="text-center">
            <div className="w-12 h-12 bg-white rounded-xl shadow-sm flex items-center justify-center mx-auto mb-2">
              <Download className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-sm text-gray-600">下载</p>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-400 mt-8">
          工具仅供学习使用，请遵守相关法律法规
        </p>
      </div>
    </div>
  );
}
