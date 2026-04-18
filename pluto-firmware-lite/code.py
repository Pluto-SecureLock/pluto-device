import time
from application_context_lite import ApplicationContextLite  # type: ignore

def main():
    app_context = ApplicationContextLite()
    while True:
        app_context.update()
        time.sleep(0.05)

if __name__ == '__main__':
    main()