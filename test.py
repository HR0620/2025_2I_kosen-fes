import pygame
pygame.init()
pygame.mixer.init()

try:
    pygame.mixer.music.load("The Dark Eternal Night.mp3")
    pygame.mixer.music.play()
    print("🎵 再生開始")
except Exception as e:
    print(f"[ERROR] {e}")

# 5秒待機
import time
time.sleep(5)
