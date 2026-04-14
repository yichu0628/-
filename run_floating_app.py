"""
桌面应用启动脚本
用于启动新版流光 Glance 桌面界面。
"""


def main():
    """
    启动桌面主界面。

    Args:
        无。

    Returns:
        None - 无返回值。
    """
    from floating_app import FloatingWidget

    print("正在启动流光 Glance 桌面端...")
    FloatingWidget()


if __name__ == "__main__":
    main()
