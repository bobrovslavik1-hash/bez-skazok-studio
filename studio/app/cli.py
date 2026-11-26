"""Команды для сервера.
  python -m app.cli set-password <логин>   — задать или сменить пароль (спросит дважды, на экране не видно)
  python -m app.cli mcp-url                — показать адрес MCP-входа для Claude (с токеном)
"""
import getpass
import sys

from . import auth, config, db


def main(argv: list) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == 'set-password':
        login = (argv[2] if len(argv) > 2 else input('Логин: ')).strip()
        if not login:
            print('Нужен логин')
            return 1
        while True:
            p1 = getpass.getpass('Новый пароль (не короче 10 символов, на экране не видно): ')
            if len(p1) < 10:
                print('Слишком короткий, ещё раз.')
                continue
            if getpass.getpass('Повтори пароль: ') != p1:
                print('Не совпало, ещё раз.')
                continue
            break
        db.init()
        try:
            auth.set_password(login, p1)
            db.audit('server', 'password_set', {'login': login})
        finally:
            db.close()
        print(f'✅ Пароль для «{login}» сохранён.')
        return 0
    if cmd == 'mcp-url':
        if not (config.MCP_TOKEN and config.PUBLIC_URL):
            print('MCP-вход не настроен (нет STUDIO_MCP_TOKEN или STUDIO_PUBLIC_URL)')
            return 1
        print(f'{config.PUBLIC_URL}/mcp/{config.MCP_TOKEN}')
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
