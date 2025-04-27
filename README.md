# AstrBot 服务器终端插件

该插件让您可以通过与 [AstrBot](https://astrbot.app) 对话的方式远程控制服务器。简单、安全、高效地执行终端命令，无需直接登录服务器。

## 环境要求

本插件依赖 **Tmux** 终端复用器，使用前请确保您的服务器已安装：

```bash
# Debian/Ubuntu
sudo apt install tmux

# CentOS/RHEL
sudo yum install tmux

# 更多安装方式请参考：https://github.com/tmux/tmux/wiki/Installing
```

## 使用指南

```
/terminal on  - 启动终端会话
/terminal off - 关闭当前会话
```

启动会话后，直接发送命令即可执行。会话闲置30分钟后将自动关闭。

## 权限说明

**⚠️ 安全提醒：本插件所有功能仅限管理员使用**

为保障服务器安全，终端插件的所有功能（启动会话、关闭会话、执行命令）均已设置管理员权限限制，普通用户无法使用。请在 AstrBot 管理面板中正确设置管理员权限。