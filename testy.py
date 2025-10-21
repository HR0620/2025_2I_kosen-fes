import pygame
import sys
import os
import time

pygame.init()
pygame.mixer.init()

# --- BGMファイルのパス ---
bgm_files = {
    "original": "The Dark Eternal Night.mp3",
    "mid": "zanzou no hiyu.mp3",
    "high": "Outer Space.mp3"
}

# --- BGM再生関数 ---
def play_bgm(bgm_name):
  path = bgm_files.get(bgm_name)
  if not path or not os.path.isfile(path):
    print(f"[ERROR] BGMファイルが見つかりません: {path}")
    return False
  try:
    pygame.mixer.music.load(path)
    pygame.mixer.music.play(-1)  # ループ再生
    print(f"[INFO] 再生中: {bgm_name} ({path})")
    return True
  except Exception as e:
    print(f"[ERROR] BGM再生に失敗しました: {e}")
    return False

# --- メイン ---
def main():
  running = True
  bgm_name = "original"  # テストしたいBGM名を選択
  if not play_bgm(bgm_name):
    pygame.quit()
    sys.exit()

  print("BGMが再生されているか確認してください。5秒後に終了します。")
  start_time = time.time()
  while running:
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False
    if time.time() - start_time > 5:
      running = False
    pygame.time.delay(100)

  pygame.mixer.music.stop()
  pygame.quit()
  print("テスト終了")

if __name__ == "__main__":
  main()
