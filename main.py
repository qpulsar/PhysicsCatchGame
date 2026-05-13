import pygame
import os
import sys
import argparse
import inspect
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
from game.app import Game



if __name__ == "__main__":
    # Get the project root directory
    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.abspath(os.path.dirname(__file__))
    
    # Ensure project root is in sys.path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    parser = argparse.ArgumentParser(description="FizikselB Oyunu")
    parser.add_argument("--game-id", type=int, default=None, help="Editörden seçili oyunun ID'si")
    parser.add_argument("--from-editor", action="store_true", help="Editörden başlatıldığını belirtir")
    parser.add_argument("--editor", action="store_true", help="Editörü başlatır")
    args = parser.parse_args()

    if args.editor:
        # Editörü başlat
        print("[DEBUG] Editör modu başlatılıyor...")
        try:
            import tkinter as tk
            from tkinter import messagebox
            print("[DEBUG] tkinter yüklendi.")
            
            # Bu blokta importları yapıyoruz ki hata varsa yakalayalım
            from editor.database.database import DatabaseManager
            from editor.ui.main_window import MainWindow
            import sv_ttk
            from game.core.utils import get_resource_path
            print("[DEBUG] Editör bileşenleri yüklendi.")

            root = tk.Tk()
            root.withdraw() # Ana pencere hazırlanana kadar gizle
            
            try:
                sv_ttk.set_theme("light")
            except Exception as te:
                print(f"[DEBUG] Tema yükleme hatası (yoksayıldı): {te}")
            
            db_path = get_resource_path('game_data.db')
            print(f"[DEBUG] Veritabanı yolu: {db_path}")
            db_manager = DatabaseManager(db_path)
            
            # Ana pencereyi oluştur ve göster
            app = MainWindow(root, db_manager)
            root.deiconify()
            print("[DEBUG] Editör penceresi gösteriliyor.")
            root.mainloop()
            sys.exit(0)
        except Exception as e:
            # Kritik hata: Kullanıcıya göster
            print(f"[ERROR] Editör başlatılamadı: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                import tkinter as tk
                from tkinter import messagebox
                error_root = tk.Tk()
                error_root.withdraw()
                messagebox.showerror("Editör Hatası", f"Editör başlatılamadı:\n\n{type(e).__name__}: {e}\n\nDetaylar için terminale bakın.")
                error_root.destroy()
            except Exception as me:
                print(f"[ERROR] Hata mesajı gösterilemedi: {me}")
            
            sys.exit(1)

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Fiziksel Büyüklükleri Yakala!")

    # Basit çalışma zamanı tanılama logu (doğru dosya ve sınıf mı?)
    try:
        print(f"[RunDBG] main: __file__={__file__}")
        print(f"[RunDBG] main: cwd={os.getcwd()}")
        print(f"[RunDBG] args: game_id={args.game_id}, from_editor={args.from_editor}")
        print(f"[RunDBG] Game class at: {inspect.getfile(Game)} (module={Game.__module__})")
    except Exception:
        pass

    # Editörden geldiyse seçili oyunla başla ve açılış ekranını göster
    if args.game_id:
        game = Game(screen, force_game_id=args.game_id)
        # Açılış ekranını (varsa) hemen gösterecek akışı başlat
        game.start_game(args.game_id)
    else:
        game = Game(screen)

    game.run()



