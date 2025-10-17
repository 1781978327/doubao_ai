import sys
import os
import base64
import markdown
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                             QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, 
                             QFileDialog)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from openai import OpenAI

# -------------------------- 基础配置 --------------------------
os.environ["ARK_API_KEY"] = "cbb4f72b-7880-4e53-995c-3ae71df8c313"
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

# -------------------------- 关键：强化Markdown样式（重点优化代码块） --------------------------
MARKDOWN_CSS = """
<style>
    /* 全局文本样式 */
    body {
        font-family: SimHei, Microsoft YaHei, sans-serif;
        font-size: 14px;
        line-height: 1.7;
        color: #333;
        margin: 5px;
    }
    /* 标题样式 */
    h1, h2, h3 {
        color: #2c3e50;
        margin: 15px 0 8px 0;
        border-bottom: 1px solid #eee;
        padding-bottom: 3px;
    }
    h1 { font-size: 18px; }
    h2 { font-size: 16px; }
    h3 { font-size: 15px; border-bottom: none; }
    /* 列表样式 */
    ul, ol {
        margin: 8px 0 8px 20px;
        padding-left: 10px;
    }
    li { margin: 5px 0; }
    /* 角色标签样式（用户/AI/推理） */
    .user-tag { color: #2980b9; font-weight: bold; }
    .ai-tag { color: #27ae60; font-weight: bold; }
    .reasoning-tag { color: #7f8c8d; font-weight: bold; }
    /* 状态提示样式（如“正在分析”） */
    .status { color: #95a5a6; font-style: italic; margin: 5px 0; }
    /* 核心：代码块样式（高辨识度） */
    .code-block {
        background-color: #2d2d2d;  /* 深色背景 */
        color: #f8f8f2;            /* 浅色文字（护眼） */
        font-family: Consolas, Monaco, "Courier New", monospace;  /* 强制等宽字体 */
        font-size: 12px;
        border: 1px solid #666;    /* 加粗边框 */
        border-radius: 4px;        /* 圆角 */
        padding: 12px;             /* 内边距（避免文字贴边） */
        margin: 10px 0;            /* 上下间距（与普通文本分开） */
        overflow-x: auto;          /* 横向滚动（长代码不换行） */
    }
    /* 代码块语言标签（如“Python”） */
    .code-language {
        color: #f1c40f;
        font-size: 11px;
        margin: 0 0 5px 0;
        font-weight: bold;
    }
    /* 图片选择提示 */
    .image-selected { color: #e67e22; font-weight: bold; }
</style>
"""

# -------------------------- 工具函数：处理Markdown中的代码块 --------------------------
def format_markdown_with_code(md_text):
    """
    处理原始Markdown文本，给代码块添加专属样式类
    支持 ```python ... ``` 或 ``` ... ``` 格式的代码块
    """
    import re
    # 正则匹配代码块（支持带语言和不带语言的格式）
    # 匹配规则：```[语言] 开头，``` 结尾，中间是代码内容
    code_pattern = r"```(\w*)\n(.*?)```"
    # 替换函数：将代码块转为带样式的HTML
    def replace_code(match):
        lang = match.group(1).strip()  # 语言类型（如Python）
        code_content = match.group(2).strip()  # 代码内容
        # 语言标签（如果有语言类型，显示“Python 代码”，否则显示“代码块”）
        lang_label = f"<div class='code-language'>{lang.capitalize()} 代码</div>" if lang else "<div class='code-language'>代码块</div>"
        # 代码内容（转义HTML特殊字符，避免冲突）
        code_escaped = code_content.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>").replace(" ", "&nbsp;")
        # 返回带样式的代码块HTML
        return f"{lang_label}<div class='code-block'>{code_escaped}</div>"
    # 执行替换（多行匹配，不区分大小写）
    formatted_md = re.sub(code_pattern, replace_code, md_text, flags=re.DOTALL | re.IGNORECASE)
    return formatted_md


class ApiThread(QThread):
    result_signal = pyqtSignal(str, str)  # (推理过程, 回答内容)

    def __init__(self, base64_image, question):
        super().__init__()
        self.base64_image = base64_image
        self.question = question

    def run(self):
        try:
            completion = client.chat.completions.create(
                model="doubao-seed-1-6-251015",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self.base64_image}"}},
                            {"type": "text", "text": self.question}
                        ],
                    }
                ],
                reasoning_effort="medium"
            )
            reasoning = getattr(completion.choices[0].message, 'reasoning_content', "无推理过程")
            answer = completion.choices[0].message.content
            self.result_signal.emit(reasoning, answer)
        except Exception as e:
            self.result_signal.emit(f"调用失败：{str(e)}", "")


class ImageChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base64_image = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("图片对话工具（代码块高显版）")
        self.setGeometry(100, 100, 950, 750)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # 主布局
        main_layout = QVBoxLayout()

        # 1. 图片选择区
        image_layout = QHBoxLayout()
        self.select_btn = QPushButton("选择本地图片")
        self.select_btn.clicked.connect(self.select_image)
        self.image_label = QLabel("未选择图片")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(220)
        self.image_label.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        image_layout.addWidget(self.select_btn)
        image_layout.addWidget(self.image_label, stretch=1)
        main_layout.addLayout(image_layout)

        # 2. 对话历史区（Markdown渲染，重点显示代码块）
        self.history_area = QTextEdit()
        self.history_area.setReadOnly(True)
        self.history_area.setAcceptRichText(True)
        self.history_area.setPlaceholderText("对话历史将显示在这里，代码块会以深色背景突出显示...")
        # 设置全局字体（确保中文显示正常）
        global_font = QFont("SimHei", 10)
        self.history_area.setFont(global_font)
        main_layout.addWidget(self.history_area)

        # 3. 输入区
        input_layout = QHBoxLayout()
        self.question_edit = QTextEdit()
        self.question_edit.setMaximumHeight(70)
        self.question_edit.setPlaceholderText("输入问题（支持Markdown，代码块用```包裹，如```python 代码 ```）")
        self.question_edit.setFont(global_font)
        self.send_btn = QPushButton("发送请求")
        self.send_btn.clicked.connect(self.send_question)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.question_edit, stretch=1)
        input_layout.addWidget(self.send_btn)
        main_layout.addLayout(input_layout)

        # 设置中心部件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.base64_image = self.image_to_base64(file_path)
            # 预览图片
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(
                self.image_label.width(), self.image_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            # 追加图片选择提示（带样式）
            self.append_markdown(f"<div class='image-selected'>✅ 已选择图片：{os.path.basename(file_path)}</div>\n")
            self.send_btn.setEnabled(True)

    def image_to_base64(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def send_question(self):
        question = self.question_edit.toPlainText().strip()
        if not question or not self.base64_image:
            return
        self.question_edit.clear()
        # 追加用户问题（带“用户”标签）
        self.append_markdown(f"<div class='user-tag'>👤 你：</div>{question}\n")
        # 追加AI正在分析的状态
        self.append_markdown(f"<div class='status'>🤖 AI：正在分析图片和问题...</div>\n")
        # 启动API线程
        self.api_thread = ApiThread(self.base64_image, question)
        self.api_thread.result_signal.connect(self.show_result)
        self.api_thread.start()

    def show_result(self, reasoning, answer):
        # 追加推理过程（带“推理”标签）
        self.append_markdown(f"<div class='reasoning-tag'>📝 AI推理：</div>{reasoning}\n")
        # 追加AI回答（带“AI”标签，先处理代码块样式）
        formatted_answer = format_markdown_with_code(answer)  # 关键：处理代码块
        self.append_markdown(f"<div class='ai-tag'>💡 AI回答：</div>{formatted_answer}\n\n")

    def append_markdown(self, md_text):
        """将处理后的Markdown转为HTML，追加到历史区"""
        # 1. 先处理代码块（添加样式）
        processed_md = format_markdown_with_code(md_text)
        # 2. 转换Markdown为HTML（处理标题、列表等）
        html = markdown.markdown(processed_md)
        # 3. 拼接CSS样式（确保所有样式生效）
        full_html = f"<html><head>{MARKDOWN_CSS}</head><body>{html}</body></html>"
        # 4. 保留原有内容，追加新内容（避免覆盖历史）
        current_html = self.history_area.toHtml()
        if "body></html>" in current_html:
            # 替换原有body结束标签，追加新内容
            new_html = current_html.replace("</body></html>", f"{html}</body></html>")
        else:
            # 初始状态：直接设置完整HTML
            new_html = full_html
        # 5. 更新历史区内容，并自动滚动到底部
        self.history_area.setHtml(new_html)
        self.history_area.moveCursor(self.history_area.textCursor().End)


if __name__ == "__main__":
    # 检查依赖（缺少则提示安装）
    try:
        import markdown
    except ImportError:
        print("请先安装markdown库：pip install markdown")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    window = ImageChatApp()
    window.show()
    sys.exit(app.exec_())