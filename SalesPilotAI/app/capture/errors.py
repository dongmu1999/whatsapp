"""聊天捕获的中文业务异常。"""


class CaptureError(RuntimeError):
    """聊天捕获失败的基类。"""


class CaptureUnavailableError(CaptureError):
    """当前平台或未安装组件无法提供捕获能力。"""


class WindowNotWhatsAppError(CaptureError):
    """前台窗口不是用户允许捕获的目标。"""


class CaptureFailedError(CaptureError):
    """已尝试捕获但没有得到可用消息。"""
