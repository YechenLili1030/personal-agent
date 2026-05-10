"""
PersonalAgent 后端启动入口

用法:
    python main.py
    python main.py --port 8000 --host 0.0.0.0 --reload
"""

import argparse
import uvicorn


def parse_args():
    parser = argparse.ArgumentParser(description="PersonalAgent Backend Server")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="绑定端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", default=True, help="热重载 (开发模式)")
    parser.add_argument("--no-reload", action="store_true", help="禁用热重载")
    return parser.parse_args()


def main():
    args = parse_args()
    reload = args.reload and not args.no_reload

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
