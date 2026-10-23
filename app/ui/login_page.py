"""登录页面"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpacerItem, QSizePolicy, QFrame,
)
from PySide6.QtCore import Signal, Qt

from app.database import user_exists, create_user, verify_user
from app.ui.components import logo, icon, set_feedback
from app.ui.theme import current_theme
from app.ui.materials import FrostedSurface


class LoginPage(QWidget):
    login_success = Signal(str)  # username

    def __init__(self):
        super().__init__()
        self.setObjectName("loginPage")
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(40)
        layout.setContentsMargins(32, 32, 48, 32)
        self._story = FrostedSurface(variant="hero")
        self._story.setObjectName("loginStory")
        story = QVBoxLayout(self._story)
        story.setContentsMargins(36, 36, 36, 32)
        brand = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(logo(34))
        self._brand_mark = mark
        brand.addWidget(mark)
        brand_name = QLabel("Tomato Timer")
        brand_name.setObjectName("loginBrand")
        brand.addWidget(brand_name)
        brand.addStretch()
        story.addLayout(brand)
        story.addStretch(2)
        headline = QLabel("留一点时间，\n给重要的事。")
        headline.setObjectName("loginStoryTitle")
        story.addWidget(headline)
        story.addSpacing(20)
        description = QLabel("从一次专注开始。\n记录工作与学习，也看见自己的每一点积累。")
        description.setObjectName("loginStoryCopy")
        description.setWordWrap(True)
        story.addWidget(description)
        story.addStretch(3)
        foot = QLabel("本地记录  ·  轻量常驻  ·  按你的节奏")
        foot.setObjectName("loginStoryFoot")
        story.addWidget(foot)
        layout.addWidget(self._story, 1)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setMaximumWidth(380)
        card.setMinimumWidth(300)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 24, 12, 24)
        card_layout.setSpacing(12)
        card_layout.addStretch()

        title = QLabel("欢迎回来")
        title.setObjectName("titleLabel")
        card_layout.addWidget(title)

        subtitle = QLabel("登录你的本地账户，继续今天的专注。")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(22)

        # 输入区域
        form = QVBoxLayout()
        form.setSpacing(10)

        username_label = QLabel("用户名")
        username_label.setProperty("class", "fieldLabel")
        form.addWidget(username_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("输入你的用户名")
        self.username_input.setAccessibleName("用户名")
        self.username_input.setMinimumHeight(28)
        username_label.setBuddy(self.username_input)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        form.addWidget(self.username_input)

        form.addSpacing(6)
        password_label = QLabel("密码")
        password_label.setProperty("class", "fieldLabel")
        form.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("输入密码")
        self.password_input.setAccessibleName("密码")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(28)
        password_label.setBuddy(self.password_input)
        self.password_input.returnPressed.connect(self._on_submit)
        form.addWidget(self.password_input)

        self.msg_label = QLabel("")
        self.msg_label.setObjectName("msgLabel")
        self.msg_label.setWordWrap(True)
        form.addWidget(self.msg_label)

        self.submit_btn = QPushButton("登录")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.setMinimumHeight(28)
        self.submit_btn.setIcon(icon("arrow", current_theme().colors["on_accent"]))
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self._on_submit)
        form.addWidget(self.submit_btn)
        form.addSpacing(6)
        register_hint = QLabel("第一次使用？输入新用户名和密码，即可创建本地账户。")
        register_hint.setProperty("class", "mutedLabel")
        register_hint.setWordWrap(True)
        form.addWidget(register_hint)

        card_layout.addLayout(form)
        card_layout.addStretch()
        privacy = QLabel("记录保存在这台电脑，无需联网。")
        privacy.setProperty("class", "mutedLabel")
        card_layout.addWidget(privacy)
        layout.addWidget(card, 1)

        self._update_mode()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._story.setVisible(self.width() >= 900)
        self.layout().setAlignment(Qt.AlignVCenter if self.width() >= 900 else Qt.AlignCenter)

    def _update_mode(self):
        self.submit_btn.setText("登录 / 注册")

    def refresh_theme(self):
        self._brand_mark.setPixmap(logo(34))
        self.submit_btn.setIcon(icon("arrow", current_theme().colors["on_accent"]))
        self._story.update()

    def _on_submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        set_feedback(self.msg_label, "")

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
            set_feedback(self.msg_label, f"账户 {username} 已创建", success=True)
            self.login_success.emit(username)
