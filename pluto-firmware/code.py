# main.py

import time
from application_context import ApplicationContext # type: ignore

def main():
    app_context = ApplicationContext()
    while True:
        app_context.update()
        time.sleep(0.05)
if __name__ == '__main__':
    main()