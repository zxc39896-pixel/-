import json
import time
import threading
import os
import sys
from tkinter import Tk, filedialog

from pynput import mouse, keyboard
from pynput.keyboard import Key, Controller as KeyController, Listener as KeyListener
from pynput.mouse import Button, Controller as MouseController, Listener as MouseListener
import keyboard as kb

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False
    console = None

key_controller = KeyController()
mouse_controller = MouseController()

events = []
loaded_macro = []
recording = False
playing = False
start_time = None

current_hotkey = "ctrl+shift+x"
hotkey_id = None

def on_press(key):
    global recording, start_time
    if not recording: return
    try:
        events.append({'type': 'key_press', 'key': key.char if hasattr(key, 'char') else str(key), 'time': time.time() - start_time})
    except AttributeError:
        events.append({'type': 'key_press', 'key': str(key), 'time': time.time() - start_time})

def on_release(key):
    global recording, start_time
    if not recording: return
    events.append({'type': 'key_release', 'key': key.char if hasattr(key, 'char') else str(key), 'time': time.time() - start_time})
    if key == keyboard.Key.esc:
        stop_recording()

def on_click(x, y, button, pressed):
    global recording, start_time
    if not recording: return
    events.append({'type': 'mouse_click', 'x': x, 'y': y, 'button': str(button), 'pressed': pressed, 'time': time.time() - start_time})

def on_move(x, y):
    global recording, start_time
    if not recording: return
    events.append({'type': 'mouse_move', 'x': x, 'y': y, 'time': time.time() - start_time})

def start_recording():
    global recording, start_time, events
    events = []
    recording = True
    start_time = time.time()
    show_message("🔴 ЗАПИСЬ НАЧАТА", "Нажми ESC для остановки", style="red")

def stop_recording():
    global recording
    if not recording: return
    recording = False
    show_message("⏹️ ЗАПИСЬ ОСТАНОВЛЕНА", f"Записано {len(events)} событий", style="yellow")
    save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if save_path:
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2)
        show_message("💾 СОХРАНЕНО", os.path.basename(save_path), style="green")

def import_macro():
    global loaded_macro
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Выберите файл макроса",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    root.destroy()
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_macro = json.load(f)
            show_message("📂 ИМПОРТ", f"{os.path.basename(file_path)} ({len(loaded_macro)} событий)", style="cyan")
        except Exception as e:
            show_message("❌ ОШИБКА", str(e), style="red")
    else:
        show_message("⚠️ ОТМЕНА", "Импорт отменён", style="yellow")

def play_macro():
    global playing
    if playing:
        show_message("⚠️ ПОДОЖДИТЕ", "Воспроизведение уже идёт", style="yellow")
        return
    macro_to_play = loaded_macro if loaded_macro else events
    if not macro_to_play:
        show_message("⚠️ НЕТ ДАННЫХ", "Сначала запишите макрос или импортируйте JSON", style="yellow")
        return
    
    playing = True
    show_message("▶️ ВОСПРОИЗВЕДЕНИЕ", f"Выполняется {len(macro_to_play)} событий...", style="green")
    
    def _play():
        start_play = time.time()
        for event in macro_to_play:
            wait_time = event['time'] - (time.time() - start_play)
            if wait_time > 0:
                time.sleep(wait_time)
            
            if event['type'] == 'key_press':
                key = event['key']
                if key.startswith('Key.'):
                    key_controller.press(getattr(Key, key.split('.')[1]))
                else:
                    key_controller.press(key)
            elif event['type'] == 'key_release':
                key = event['key']
                if key.startswith('Key.'):
                    key_controller.release(getattr(Key, key.split('.')[1]))
                else:
                    key_controller.release(key)
            elif event['type'] == 'mouse_click':
                btn = Button.left if 'left' in event['button'] else Button.right
                if event['pressed']:
                    mouse_controller.press(btn)
                else:
                    mouse_controller.release(btn)
            elif event['type'] == 'mouse_move':
                mouse_controller.position = (event['x'], event['y'])
        
        global playing
        playing = False
        show_message("✅ ГОТОВО", "Воспроизведение завершено", style="green")
    
    threading.Thread(target=_play, daemon=True).start()

def register_hotkey(hotkey_str):
    global hotkey_id
    try:
        if hotkey_id is not None:
            kb.remove_hotkey(hotkey_id)
        hotkey_id = kb.add_hotkey(hotkey_str, lambda: play_macro())
        return True
    except Exception as e:
        show_message("❌ ОШИБКА БИНДА", str(e), style="red")
        return False

def set_hotkey():
    global current_hotkey
    clear_screen()
    print_header()
    show_message("⌨️ НАСТРОЙКА БИНДА", 
                 f"Текущая комбинация: {current_hotkey}\n"
                 "Введите новую комбинацию (например, ctrl+shift+a или alt+f1)\n"
                 "Или оставьте пустым для отмены.", style="cyan")
    new_hotkey = input("> ").strip().lower()
    if new_hotkey:
        if register_hotkey(new_hotkey):
            current_hotkey = new_hotkey
            show_message("✅ БИНД ОБНОВЛЁН", f"Новая комбинация: {current_hotkey}", style="green")
        else:
            show_message("⚠️ НЕ УДАЛОСЬ", "Проверьте синтаксис комбинации", style="yellow")
    else:
        show_message("ℹ️ ОТМЕНА", "Бинд не изменён", style="cyan")
    input("\nНажмите Enter чтобы вернуться...")

def show_message(title, message, style="white"):
    if USE_RICH:
        color = style
        if style == "red": color = "bold red"
        elif style == "green": color = "bold green"
        elif style == "yellow": color = "bold yellow"
        elif style == "cyan": color = "bold cyan"
        console.print(Panel(f"[{color}]{message}[/]", title=f"[bold]{title}[/]", border_style=style))
    else:
        print(f"\n--- {title} ---")
        print(message)
        print("-" * (len(title) + 6))

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    if USE_RICH:
        title = Text("⚡ MACROS v1.1 ⚡", style="bold blue")
        console.print(Panel(title, border_style="blue"))
        console.print("[dim]Управление макросами для автоматизации[/dim]")
        console.print(f"[dim]Глобальный бинд: [bold]{current_hotkey}[/bold][/dim]\n")
    else:
        print("=" * 40)
        print("       MACROS v1.1")
        print(f"Глобальный бинд: {current_hotkey}")
        print("=" * 40)

def print_menu():
    if USE_RICH:
        table = Table(show_header=False, box=None)
        table.add_row("[1]", "🎬 Начать запись")
        table.add_row("[2]", "⏹️ Остановить запись и сохранить")
        table.add_row("[3]", "▶️ Воспроизвести макрос")
        table.add_row("[4]", "📂 Импортировать макрос из JSON")
        table.add_row("[5]", "⌨️ Назначить горячую клавишу")
        table.add_row("[6]", "🚪 Выход")
        console.print(table)
    else:
        print("\nВыберите действие:")
        print("1. Начать запись")
        print("2. Остановить запись и сохранить")
        print("3. Воспроизвести макрос")
        print("4. Импортировать макрос из JSON")
        print("5. Назначить горячую клавишу")
        print("6. Выход")

listener_key = KeyListener(on_press=on_press, on_release=on_release)
listener_mouse = MouseListener(on_click=on_click, on_move=on_move)

def start_listeners():
    listener_key.start()
    listener_mouse.start()

def main():
    global current_hotkey
    clear_screen()
    print_header()
    start_listeners()
    register_hotkey(current_hotkey)
    
    while True:
        print_menu()
        try:
            choice = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        
        if choice == '1':
            clear_screen()
            print_header()
            start_recording()
            input("\nНажмите Enter чтобы вернуться в меню...")
            clear_screen()
            print_header()
        elif choice == '2':
            if recording:
                stop_recording()
            else:
                show_message("⚠️ ВНИМАНИЕ", "Сейчас запись не идёт", style="yellow")
            input("\nНажмите Enter чтобы продолжить...")
            clear_screen()
            print_header()
        elif choice == '3':
            play_macro()
            input("\nНажмите Enter чтобы продолжить...")
            clear_screen()
            print_header()
        elif choice == '4':
            import_macro()
            input("\nНажмите Enter чтобы продолжить...")
            clear_screen()
            print_header()
        elif choice == '5':
            set_hotkey()
            clear_screen()
            print_header()
        elif choice == '6':
            show_message("👋 ДО СВИДАНИЯ", "Выход из программы", style="cyan")
            break
        else:
            show_message("❓ НЕИЗВЕСТНО", "Пожалуйста, выберите цифру от 1 до 6", style="red")
            input("\nНажмите Enter чтобы продолжить...")
            clear_screen()
            print_header()

if __name__ == "__main__":
    main()
    listener_key.stop()
    listener_mouse.stop()
    sys.exit(0)