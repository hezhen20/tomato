"""登录页面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpacerItem, QSizePolicy, QFrame,
)
from PySide6.QtCore import Signal, Qt

from app.database import user_exists, create_user, verify_user


class LoginPage(QWidget):
    login_success = Signal(str)  # username

    def __init__(self):
        super().__init__()
        self.setObjectName("loginPage")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(0)
        layout.setContentsMargins(28, 28, 28, 28)

        layout.addSpacerItem(QSpacerItem(0, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        card = QFrame()
        card.setObjectName("loginCard")
        card.setMaximumWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 30, 28, 28)
        card_layout.setSpacing(14)

        title = QLabel("Tomato Timer")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("轻量的桌面时间追踪工具")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(18)

        # 输入区域
        form = QVBoxLayout()
        form.setSpacing(14)
        form.setAlignment(Qt.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("用户名")
        self.username_input.setFixedWidth(300)
        form.addWidget(self.username_input, alignment=Qt.AlignCenter)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setFixedWidth(300)
        self.password_input.returnPressed.connect(self._on_submit)
        form.addWidget(self.password_input, alignment=Qt.AlignCenter)

        self.msg_label = QLabel("")
        self.msg_label.setObjectName("msgLabel")
        self.msg_label.setAlignment(Qt.AlignCenter)
        form.addWidget(self.msg_label)

        self.submit_btn = QPushButton("登录")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.setFixedWidth(300)
        self.submit_btn.clicked.connect(self._on_submit)
        form.addWidget(self.submit_btn, alignment=Qt.AlignCenter)

        card_layout.addLayout(form)
        layout.addWidget(card, alignment=Qt.AlignCenter)
        layout.addSpacerItem(QSpacerItem(0, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self._update_mode()

    def _update_mode(self):
        self.submit_btn.setText("登录 / 注册")

    def _on_submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self.msg_label.setText("请输入用户名和密码")
            return

        if user_exists(username):
            # 用户名已存在，验证密码
            if verify_user(username, password):
                self.login_success.emit(username)
            else:
                self.msg_label.setText("密码错误")
        else:
            # 新用户名，自动注册
            create_user(username, password)
            self.msg_label.setStyleSheet("color: #00F5A0;")
            self.msg_label.setText(f"账户 {username} 已创建")
            self.login_success.emit(username)
