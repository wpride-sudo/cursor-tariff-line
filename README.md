# Cursor plan usage line

Shows a Cursor agent line like “Allowed 76%, now 74% +1” only when the plan usage percent goes up.

![Usage line in the agent window](images/usage-line.png)

## What you see

The line appears once in the agent reply when the spent share of the plan increases. Example: it was 73% and became 74%. The reply shows “Allowed 76%, now 74%” with “+1” in red on the right.

If the percent did not go up, there is no line. Run the `show-usage` command when you want Allowed and Now immediately.

The line is small and not bold.

- Green when Now is below Allowed.
- Red when Now is equal to Allowed or higher.
- The difference on the right is always red and appears only in that one reply.

## How the numbers are calculated

Allowed spreads the plan evenly from the reset day in `.cursor/hooks/config.json` (`resetDay`, 27 by default). It is the days since the previous reset divided by the days until the next one. On 23 October, with reset day 27, that is 26 of 30 days, or 86%. In a short month the reset falls on the last day. You can also set `CURSOR_USAGE_RESET_DAY`.

Now is the current Cursor plan usage percent, rounded to a whole number.

The increase is measured from the last saved Now value. A drop does not show the line.

## Set the reset day in Cursor

1. In Cursor press `Ctrl+P` (`Cmd+P` on macOS) and open `.cursor/hooks/config.json`.
2. Set `resetDay` to the day of the month when your counter resets, from 1 to 31.

```json
{
  "resetDay": 27
}
```

3. Save the file. The next agent message uses the new day.

If the hooks are installed for every project, edit the same `resetDay` in the user file instead: `%USERPROFILE%\.cursor\hooks\config.json` on Windows, or `~/.cursor/hooks/config.json` on macOS and Linux.

## Show the current percent now

In the agent chat type `/show-usage` and send it. Cursor shows Allowed and Now even when the percent did not go up. That reply has no red `+1`.

## Files

- `.cursor/hooks.json` starts the check at session start and before each message.
- `.cursor/hooks/show-usage.py` reads plan usage and decides whether it increased.
- `.cursor/rules/show-date.mdc` tells the agent how to draw the line.
- `.cursor/commands/show-usage.md` shows Allowed and Now on request.
- `.cursor/hooks/config.json` sets `resetDay`.
- `.cursor-plugin/plugin.json` is the Cursor plugin manifest.

GitHub topics: `cursor`, `usage`, `hooks`.

## Install in one project

You need Python on `PATH` (`python`, or `python.exe` on Windows) and an active Cursor sign-in. This works on Windows, macOS, and Linux.

Copy the `.cursor` folder into the project root. Set `resetDay` in `.cursor/hooks/config.json`. Open a new agent chat. An existing chat does not pick up the rule.

To install it as a plugin, use this repository. The manifest is `.cursor-plugin/plugin.json`.

## Install for every project

Copy `show-usage.py` and `config.json` to the user hooks folder:

- Windows: `%USERPROFILE%\.cursor\hooks\`
- macOS and Linux: `~/.cursor/hooks/`

Create `hooks.json` in `~/.cursor` on macOS and Linux, or `%USERPROFILE%\.cursor\hooks.json` on Windows:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "python ./hooks/show-usage.py"
      }
    ],
    "beforeSubmitPrompt": [
      {
        "command": "python ./hooks/show-usage.py"
      }
    ]
  }
}
```

On Windows, change `python` to `python.exe` if the hook does not start. The rule `.cursor/rules/show-date.mdc` and the command `.cursor/commands/show-usage.md` still have to be placed in each project where the agent should draw the line.

# Строка расхода тарифа Cursor

Показывает в окне агента Cursor строку «Allowed 76%, now 74% +1» только в тот момент, когда процент расхода тарифа вырос.

![Строка расхода в окне агента](images/usage-line.png)

## Что видит пользователь

Строка появляется в ответе агента один раз, когда доля потраченного тарифа увеличилась. Пример: было 73%, стало 74%. В ответе будет «Allowed 76%, now 74%» и справа красным «+1».

Если процент не вырос, строки нет. Команда `show-usage` показывает Allowed и Now в любой момент.

Строка маленькая, без жирного шрифта.

- Зелёная, если Now меньше, чем Allowed.
- Красная, если Now равно Allowed или больше.
- Разница справа всегда красная и показывается только в этом одном ответе.

## Как считаются числа

Allowed распределяет тариф равномерно от дня в `.cursor/hooks/config.json` (`resetDay`, по умолчанию 27). Это дни с прошлого обновления, делённые на дни до следующего. Для 23 октября при дне 27 это 26 дней из 30, то есть 86%. В коротком месяце обновление приходится на последний день. День можно задать и переменной `CURSOR_USAGE_RESET_DAY`.

Now — общий процент расхода текущего тарифа Cursor, округлённый до целого.

Прирост считается от предыдущего сохранённого значения Now. Падение процента строку не показывает.

## Как указать день месяца в Cursor

1. В Cursor нажмите `Ctrl+P` (`Cmd+P` на macOS) и откройте `.cursor/hooks/config.json`.
2. Запишите в `resetDay` день месяца, когда обновляется счётчик, от 1 до 31.

```json
{
  "resetDay": 27
}
```

3. Сохраните файл. Следующее сообщение агента возьмёт новый день.

Если хуки стоят для всех проектов, тот же `resetDay` меняйте в пользовательском файле: `%USERPROFILE%\.cursor\hooks\config.json` на Windows или `~/.cursor/hooks/config.json` на macOS и Linux.

## Как принудительно показать текущий процент

В чате агента наберите `/show-usage` и отправьте. Cursor покажет Allowed и Now, даже если процент не вырос. В этом ответе красного `+1` не будет.

## Состав

- `.cursor/hooks.json` запускает расчёт в начале сессии и перед каждым сообщением.
- `.cursor/hooks/show-usage.py` читает расход тарифа и решает, был ли прирост.
- `.cursor/rules/show-date.mdc` говорит агенту, как нарисовать строку.
- `.cursor/commands/show-usage.md` показывает Allowed и Now по запросу.
- `.cursor/hooks/config.json` задаёт `resetDay`.
- `.cursor-plugin/plugin.json` — манифест плагина Cursor.

Темы GitHub: `cursor`, `usage`, `hooks`.

## Установка в один проект

Нужны Python в `PATH` (`python`, на Windows можно `python.exe`) и вход в Cursor. Работает на Windows, macOS и Linux.

Скопируйте папку `.cursor` в корень проекта. Укажите `resetDay` в `.cursor/hooks/config.json`. Откройте новый чат агента. Старый чат это правило не подхватит.

Чтобы поставить как плагин, используйте этот репозиторий. Манифест лежит в `.cursor-plugin/plugin.json`.

## Установка для всех проектов

Скопируйте `show-usage.py` и `config.json` в папку хуков пользователя:

- Windows: `%USERPROFILE%\.cursor\hooks\`
- macOS и Linux: `~/.cursor/hooks/`

Создайте `hooks.json` в `~/.cursor` на macOS и Linux или `%USERPROFILE%\.cursor\hooks.json` на Windows:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "python ./hooks/show-usage.py"
      }
    ],
    "beforeSubmitPrompt": [
      {
        "command": "python ./hooks/show-usage.py"
      }
    ]
  }
}
```

На Windows замените `python` на `python.exe`, если хук не запускается. Правило `.cursor/rules/show-date.mdc` и команду `.cursor/commands/show-usage.md` всё равно нужно положить в каждый проект, где агент должен рисовать строку.
