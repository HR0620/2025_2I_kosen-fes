import os
import pygame
import sys
import math
import time
import random

pygame.init()
pygame.mixer.init()

# --- 定数設定 ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = SCREEN_WIDTH * 10 // 16     # 16:10 アスペクト比
FPS = 60
CAMERA_WIDTH_2P = 375     # 2P（分割画面）用のカメラ幅
CAMERA_HEIGHT = 400       # 基本のカメラ高さ
# 1P（フルスクリーン）用のカメラ幅
CAMERA_WIDTH_1P = int(CAMERA_HEIGHT * (SCREEN_WIDTH / SCREEN_HEIGHT))

TIME_LIMIT = 300     # 制限時間（秒）
GOAL_Y = 30000.0     # ゴールY座標
ZOOM_OUT_SCALE = 0.5
ZOOM_SMOOTHING = 0.1

IMAGE_PATH = "./hisayoshi/image"
SOUND_PATH = "./hisayoshi/sound"
BGM_PATH = f"{SOUND_PATH}/bgm"
EFFECT_PATH = f"{SOUND_PATH}/effect"
VOICE_PATH = f"{SOUND_PATH}/voice"

FONT_PATH = "./hisayoshi/font/NotoSansJP-VariableFont_wght.ttf"  # フォントファイルのパス

# 既存のフォントサイズ
FONT_SIZE_SMALL = 36
FONT_SIZE_BUTTON = 48
FONT_SIZE_TITLE = 72

# --- Chat Box/Teacher Messages ---
TEACHER_MESSAGES = [
    "焦らず、一歩ずつ進みなさい。",
    "落ちてもめげずに、学びとして活かしなさい。",
    "壁ジャンプをうまく使いこなせていますね！",
    "目標は遠くても、必ずたどり着けますよ。",
    "マップの構造をよく見て、次の足場を見つけましょう。",
    "落ち着いて。急ぎすぎると足元をすくわれますよ。",
    "その調子です、着実に高さを稼いでいます！",
]

TORUS_RESPONSE = (
    "「ダブルトーラス」という概念に興味を持たれたようですね。これは、"
    "数学的、特にトポロジーの分野で使われる概念です。ドーナツ型（トーラス）の"
    "物体が2つつながったような形状、つまり穴が2つある図形を指します。トポロジーでは、"
    "物体の「穴の数」（種数）が非常に重要で、ダブルトーラスは種数2の閉曲面です。"
    "コーヒーカップとドーナツが同じトポロジーであるように、この形状も変形によって"
    "多くの異なる形を取り得ますが、穴の数だけは変わりません。あなたが今登っている"
    "この世界も、もしかしたら高次元のトポロジーを持っているのかもしれませんね。"
)

# --- フォント初期化の修正 (日本語対応のロバスト化) ---
try:
  # 3つのフォントオブジェクトをグローバルスコープで定義
  font = pygame.font.Font(FONT_PATH, FONT_SIZE_SMALL)
  button_font = pygame.font.Font(FONT_PATH, FONT_SIZE_BUTTON)
  title_font = pygame.font.Font(FONT_PATH, FONT_SIZE_TITLE)
except FileNotFoundError:
  print(f"[WARNING] 日本語フォントファイルが見つかりません: {FONT_PATH}。システムフォントにフォールバックします。")

  # 日本語対応システムフォントの候補リスト
  japanese_fonts = ["meiryo", "hiragino sans",
                    "ms gothic", "noto sans cjk jp", "arial unicode ms"]

  loaded_font = False
  for font_name in japanese_fonts:
    try:
      # 各フォント名でロードを試みる
      font = pygame.font.SysFont(font_name, FONT_SIZE_SMALL)
      button_font = pygame.font.SysFont(font_name, FONT_SIZE_BUTTON)
      title_font = pygame.font.SysFont(font_name, FONT_SIZE_TITLE)
      loaded_font = True
      print(f"[INFO] システムフォント '{font_name}' を使用します。")
      break
    except Exception:
      continue  # 次のフォントを試す

  if not loaded_font:
      # 全て失敗した場合、最終フォールバック
    print(f"[ERROR] 日本語フォントのロードに失敗しました。デフォルトフォントを使用します。")
    font = pygame.font.SysFont(None, FONT_SIZE_SMALL)
    button_font = pygame.font.SysFont(None, FONT_SIZE_BUTTON)
    title_font = pygame.font.SysFont(None, FONT_SIZE_TITLE)

except Exception as e:
  print(f"[ERROR] フォント読み込み中に予期せぬエラーが発生しました: {e}。デフォルトフォントを使用します。")
  font = pygame.font.SysFont(None, FONT_SIZE_SMALL)
  button_font = pygame.font.SysFont(None, FONT_SIZE_BUTTON)
  title_font = pygame.font.SysFont(None, FONT_SIZE_TITLE)


# --- ゲーム画面の初期化 ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("OnlyUp-style Game (1P/2P)")
clock = pygame.time.Clock()

# キーリピート設定 (テキスト入力用) --- メインループ前で設定
pygame.key.set_repeat(500, 50)

# --- アセットのロード (一元管理) ---


def load_image(filename):
  # 画像ファイルをロードし、エラー処理を行うヘルパー関数
  try:
    return pygame.image.load(f"{IMAGE_PATH}/{filename}").convert_alpha()
  except pygame.error as e:
    print(f"Error loading {filename}: {e}.")
    return None


# 新機能に必要な画像をロード
opening_image = load_image("opening_color.png")
loading_background = load_image("manga_topology.png")

# 既存の画像をロード
map_image = load_image("map_highres.png")
if not map_image:
  pygame.quit()
  sys.exit()

original_image = load_image("muroya.png")
if not original_image:
  pygame.quit()
  sys.exit()

MAP_WIDTH, MAP_HEIGHT = map_image.get_size()


def load_voice_files():
    # hisayoshi/sound/voice フォルダ内の全てのmp3をロードして辞書で返す
  voices = {}
  if not os.path.exists(VOICE_PATH):
    print(f"[WARNING] VOICE_PATH not found: {VOICE_PATH}")
    return voices

  for file in os.listdir(VOICE_PATH):
    if file.lower().endswith(".mp3"):
      name = os.path.splitext(file)[0]
      full_path = os.path.join(VOICE_PATH, file)
      try:
        voices[name] = pygame.mixer.Sound(full_path)
      except pygame.error as e:
        print(f"[ERROR] Failed to load {file}: {e}")
  print(f"[INFO] Loaded {len(voices)} voice files.")
  return voices


voice_dict = load_voice_files()

# --- サウンド設定とチャンネル ---
try:
    # ファイル名が変更されている可能性を考慮して修正
  jump_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/kick.mp3")
  blue_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/boyon.mp3")
  green_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/explosion.mp3")
  fall_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/landing.mp3")
  wind_sound = pygame.mixer.Sound(
      f"{EFFECT_PATH}/Wind-Synthetic_Ambi01-1.mp3")
except pygame.error as e:
  print(
      f"Error loading sound files. Check file paths and formats: {e}. Some sounds may not play.")
  # ロードに失敗したサウンドにはNoneを割り当て
  jump_sound = blue_sound = green_sound = fall_sound = wind_sound = None

# チャンネル割り当て (SFXと風音)
CHANNEL_P1_SFX = pygame.mixer.Channel(0)
CHANNEL_P2_SFX = pygame.mixer.Channel(1)
CHANNEL_P1_WIND = pygame.mixer.Channel(2)
CHANNEL_P2_WIND = pygame.mixer.Channel(3)

# 風音のループ再生を開始 (初期音量 0.0)
if wind_sound:
  CHANNEL_P1_WIND.play(wind_sound, loops=-1)
  CHANNEL_P2_WIND.play(wind_sound, loops=-1)
  CHANNEL_P1_WIND.set_volume(0.0)
  CHANNEL_P2_WIND.set_volume(0.0)

# --- プレイヤー画像の設定 ---
scaled_image = pygame.transform.scale(original_image, (100, 150))
image_right = scaled_image
image_left = pygame.transform.flip(scaled_image, True, False)

# 1/20 に縮小した全体マップ
overview_width = 120
overview_height = int(MAP_HEIGHT * (overview_width / MAP_WIDTH))
map_overview = pygame.transform.scale(
    map_image, (overview_width, overview_height))


# --- Player クラス ---
class Player:
  def __init__(self, player_id, image_right, image_left, start_x, sfx_channel, wind_channel):
    self.player_id = player_id
    self.x = start_x
    self.y = 200.0
    self.width = 20
    self.height = 30
    self.vx = 0.0
    self.vy = 0.0
    self.speed = 2.5
    self.jump_speed = 3.24
    self.gravity = 0.075
    self.on_ground = False
    self.wall_jump_cooldown = 0
    self.is_goal = False

    self.facing_right = True
    # ↓絶対に変えない↓
    self.image_right = image_left
    self.image_left = image_right
 # ↑絶対に変えない↑
    self.sfx_channel = sfx_channel
    self.wind_channel = wind_channel
    self.is_zooming_out = False

  def play_sound(self, sound):
    if sound and self.sfx_channel:
      self.sfx_channel.play(sound)

  def update(self, keys, control_map):
    if self.is_goal:
      return

    # ズームアウトキーの状態チェック
    zoom_key = control_map.get('zoom_out')
    if zoom_key is not None:
      self.is_zooming_out = keys[zoom_key]
    else:
      self.is_zooming_out = False

    accel = 0.375 if self.on_ground else 0.025
    max_speed = self.speed

    # 落下速度に応じて風音の音量を調整
    if self.vy < -1.0:
      speed_factor = min(abs(self.vy) / 10, 1.0)
      if self.wind_channel:
        self.wind_channel.set_volume(speed_factor * 0.8)
    else:
      if self.wind_channel:
        self.wind_channel.set_volume(0.0)

    # 水平移動入力
    left_keys = [control_map.get('left')]
    right_keys = [control_map.get('right')]
    jump_keys = [control_map.get('jump')]

    is_moving_left = any(key is not None and keys[key] for key in left_keys)
    is_moving_right = any(key is not None and keys[key] for key in right_keys)
    is_jumping = any(key is not None and keys[key] for key in jump_keys)

    if is_moving_left:
      self.vx -= accel
      self.facing_right = False
    elif is_moving_right:
      self.vx += accel
      self.facing_right = True
    else:
      if self.vx > 0:
        self.vx = max(0, self.vx - accel)
      elif self.vx < 0:
        self.vx = min(0, self.vx + accel)

    self.vx = max(-max_speed, min(self.vx, max_speed))

    # ジャンプ処理
    if is_jumping:
      if self.on_ground:
          # 地上ジャンプ
        self.vy = self.jump_speed
        self.on_ground = False
        self.play_sound(jump_sound)
        if "yoisho" in voice_dict:
          voice_dict["yoisho"].play()
      elif self.wall_jump_cooldown == 0:
          # 壁ジャンプの判定
        if self.check_collision(self.x - 0.2, self.y) or self.check_collision(self.x + 0.2, self.y):
          self.vy = self.jump_speed * 0.8
          if self.check_collision(self.x - 0.2, self.y):
            self.vx = self.speed * 0.7     # 右壁から左へ
            self.facing_right = True
          else:
            self.vx = -self.speed * 0.7     # 左壁から右へ
            self.facing_right = False
          self.wall_jump_cooldown = 10
          self.play_sound(jump_sound)
          if "yoisho" in voice_dict:
            voice_dict["yoisho"].play()

    if self.wall_jump_cooldown > 0:
      self.wall_jump_cooldown -= 1

    self.vy -= self.gravity
    new_x = self.x + self.vx
    new_y = self.y + self.vy

    # X方向の衝突判定と移動
    if not self.check_collision(new_x, self.y):
      self.x = new_x
    else:
      self.vx = 0

    # Y方向の衝突判定と移動
    if not self.check_collision(self.x, new_y):
      self.y = new_y
      self.on_ground = False
    else:
        # 着地判定
      if self.vy < 0:
        if not self.on_ground:
          self.play_sound(fall_sound)
        self.on_ground = True
      self.vy = 0

    # 画面外に出ないようにクランプ
    self.x = max(0, min(self.x, MAP_WIDTH - self.width))
    self.y = max(0, self.y)

    # ゴール判定
    if self.y >= GOAL_Y:
      self.is_goal = True
      self.vy = 0
      self.vx = 0

    # 特殊ジャンプのチェック
    special = self.check_special_jump()
    if special == 'blue':
      self.vy = 8.66
      self.play_sound(blue_sound)
    elif special == 'green':
      self.vy = 17.32
      self.play_sound(green_sound)

  def check_collision(self, x, y):
      # 当たり判定 (黒い部分)
    left = int(x)
    right = int(math.ceil(x + self.width))
    bottom = int(y)
    top = int(math.ceil(y + self.height))

    for px in range(left, right):
      for py in range(bottom, top):
        if 0 <= px < MAP_WIDTH and 0 <= py < MAP_HEIGHT:
          img_y = MAP_HEIGHT - py - 1
          try:
              # R, G, Bがほぼ0で、アルファ値が0より大きい場合を衝突とする (黒)
            if map_image.get_at((px, img_y))[:3] == (0, 0, 0):
              return True
          except IndexError:
            pass
    return False

  def draw(self, surface, cam_x, cam_y, screen_width, screen_height, camera_width, camera_height, zoom):
      # プレイヤーの描画
    scale_x = screen_width / camera_width
    scale_y = screen_height / camera_height

    screen_x = (self.x - cam_x) * scale_x
    screen_y = screen_height - \
        ((self.y - cam_y) * scale_y) - self.height * scale_y

    image = self.image_right if self.facing_right else self.image_left

    scaled_image = pygame.transform.scale(
        image, (int(self.width * scale_x), int(self.height * scale_y)))
    surface.blit(scaled_image, (screen_x, screen_y))

  def check_special_jump(self):
      # 特殊ジャンプ床（青または緑）のチェック
    left = int(self.x)
    right = int(math.ceil(self.x + self.width))
    bottom = int(self.y)
    top = int(math.ceil(self.y + self.height))

    for px in range(left, right):
      for py in range(bottom, top):
        if 0 <= px < MAP_WIDTH and 0 <= py < MAP_HEIGHT:
          img_y = MAP_HEIGHT - py - 1
          try:
            r, g, b, a = map_image.get_at((px, img_y))
            if r == 0 and g == 0 and b == 255:
              return 'blue'
            elif r == 0 and g == 255 and b == 0:
              return 'green'
          except IndexError:
            pass
    return None


# --- Camera クラス ---
class Camera:
  def __init__(self, camera_width, camera_height):
    self.x = 0
    self.y = 0
    self.CAMERA_WIDTH = camera_width
    self.CAMERA_HEIGHT = camera_height

  def update(self, player, smoothing, zoom_scale):
      # ズーム率を考慮した表示幅と表示高さを計算
    target_display_width = self.CAMERA_WIDTH / zoom_scale
    target_display_height = self.CAMERA_HEIGHT / zoom_scale

    # ターゲットの中心座標を計算
    target_x = player.x + player.width / 2 - target_display_width / 2
    target_y = player.y + player.height / 2 - target_display_height / 2

    # カメラがマップ外に出ないようにクランプ
    target_x = max(0, min(target_x, MAP_WIDTH - target_display_width))
    target_y = max(0, min(target_y, MAP_HEIGHT - target_display_height))

    # スムージングを適用
    self.x += (target_x - self.x) * smoothing
    self.y += (target_y - self.y) * smoothing


# --- ヘルパー関数 ---
def draw_text_border(surface, text, font, color, border_color, x, y, border_size=1):
    # テキストを縁付きで描画するヘルパー関数
  for dx in range(-border_size, border_size + 1):
    for dy in range(-border_size, border_size + 1):
      if dx != 0 or dy != 0:
        border_surface = font.render(text, True, border_color)
        surface.blit(border_surface, (x + dx, y + dy))
  text_surface = font.render(text, True, color)
  surface.blit(text_surface, (x, y))


def switch_bgm(target, current_bgm):
    # BGMを切り替える (pygame.mixer.musicを使用)
  if target != current_bgm:
    try:
      if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

      bgm_file = ""
      # ファイル名のハイフン化を修正: Python文字列内での置換は行わない
      if target == "original":
        bgm_file = f"{BGM_PATH}/The-Dark-Eternal-Night.mp3"
      elif target == "mid":
        bgm_file = f"{BGM_PATH}/zanzou-no-hiyu.mp3"
      elif target == "high":
        bgm_file = f"{BGM_PATH}/Outer-Space.mp3"

      if bgm_file:
        pygame.mixer.music.load(bgm_file)
        pygame.mixer.music.play(-1, fade_ms=2000)
        return target
      else:
        return current_bgm
    except Exception as e:
      print(f"[ERROR] Failed to load/play BGM: {e}")
      return current_bgm
  return current_bgm


def draw_overview_map(main_surface, player1, player2, ow_width, ow_height, map_w, map_h, font, overview_rect):
    # 全体マップ（オーバービュー）を描画するヘルパー関数
  overview_surface = pygame.Surface((ow_width, ow_height), pygame.SRCALPHA)
  overview_surface.set_alpha(200)
  overview_surface.blit(map_overview, (0, 0))
  main_surface.blit(overview_surface, overview_rect)
  pygame.draw.rect(main_surface, (255, 255, 255), overview_rect, 2)
  scale_x = ow_width / map_w
  scale_y = ow_height / map_h
  PLAYER_DOT_RADIUS = 4
  BORDER_COLOR = (255, 215, 0)     # P1のドット（枠）
  player1_dot_x = int(player1.x * scale_x)
  player1_dot_y = int((map_h - player1.y) * scale_y)
  dot_pos1 = (overview_rect.left + player1_dot_x,
              overview_rect.top + player1_dot_y)
  pygame.draw.circle(main_surface, BORDER_COLOR, dot_pos1, 6)
  pygame.draw.circle(main_surface, (255, 0, 0), dot_pos1, PLAYER_DOT_RADIUS)
  if player2:  # P2のドット（青）
    player2_dot_x = int(player2.x * scale_x)
    player2_dot_y = int((map_h - player2.y) * scale_y)
    dot_pos2 = (overview_rect.left + player2_dot_x,
                overview_rect.top + player2_dot_y)
    pygame.draw.circle(main_surface, BORDER_COLOR, dot_pos2, 6)
    pygame.draw.circle(main_surface, (0, 0, 255),
                       dot_pos2, PLAYER_DOT_RADIUS)
  # ゴールラインの描画
  goal_y_on_map = map_h - GOAL_Y
  goal_line_y = int(goal_y_on_map * scale_y)
  line_y_pos = overview_rect.top + goal_line_y
  if overview_rect.top < line_y_pos < overview_rect.bottom:
    pygame.draw.line(main_surface, (255, 255, 0), (overview_rect.left,
                                                   line_y_pos), (overview_rect.right, line_y_pos), 2)
    text_goal = font.render("GOAL", True, (255, 255, 0))
    main_surface.blit(text_goal, (overview_rect.left,
                                  line_y_pos - text_goal.get_height() - 2))


def draw_game_view(surface, player, camera, cam_width, cam_height, zoom_scale, player_label, font):
    # 個別のゲーム画面を描画するヘルパー関数
  display_width = cam_width / zoom_scale
  display_height = cam_height / zoom_scale
  rect_x = int(camera.x)
  rect_y = MAP_HEIGHT - int(camera.y) - int(display_height)
  camera_rect = pygame.Rect(rect_x, rect_y, int(
      display_width), int(display_height))
  camera_rect.clamp_ip(pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))
  sub_map = map_image.subsurface(camera_rect)
  scaled_map = pygame.transform.scale(
      sub_map, (surface.get_width(), surface.get_height()))
  surface.blit(scaled_map, (0, 0))
  player.draw(surface, camera.x, camera.y, surface.get_width(),
              surface.get_height(), display_width, display_height, zoom_scale)

  if player_label:
    player_id_color = (255, 0, 0) if player.player_id == 1 else (0, 0, 255)
    draw_text_border(surface, player_label, font,
                     player_id_color, (255, 255, 255), 10, 10, border_size=2)

  text_pos = font.render(
      f"Pos: ({int(player.x)}, {int(player.y)})", True, (255, 255, 255))
  surface.blit(text_pos, (surface.get_width() - text_pos.get_width() - 10, 10))


def draw_end_screen(surface, message, font):
    # ゲームオーバー画面を描画
  surface.fill((0, 0, 0))
  text_render = font.render(message, True, (255, 255, 255))
  rect = text_render.get_rect(
      center=(surface.get_width() // 2, surface.get_height() // 2))
  surface.blit(text_render, rect)
  pygame.display.flip()
  time.sleep(3)


def draw_select_mode_screen(surface, title_font, button_font, btn_1p_rect, btn_2p_rect, btn_manual_rect, current_state):
    # モード選択画面を描画
  surface.fill((30, 30, 50))     # 濃い青の背景
  title_text = "Select Game Mode"
  title_width = title_font.size(title_text)[0]
  draw_text_border(surface, title_text, title_font, (255, 255, 255), (0, 0, 0),
                   surface.get_width() // 2 - title_width // 2,
                   surface.get_height() // 5, 2)

  if current_state == "MAIN_SELECT":
      # 1P ボタン
    pygame.draw.rect(surface, (0, 100, 200), btn_1p_rect, border_radius=10)
    pygame.draw.rect(surface, (255, 255, 255), btn_1p_rect, 3, border_radius=10)
    btn_1p_text = button_font.render("シングルプレイ", True, (255, 255, 255))
    surface.blit(btn_1p_text, btn_1p_text.get_rect(center=btn_1p_rect.center))
    # 2P ボタン
    pygame.draw.rect(surface, (200, 0, 100), btn_2p_rect, border_radius=10)
    pygame.draw.rect(surface, (255, 255, 255), btn_2p_rect, 3, border_radius=10)
    btn_2p_text = button_font.render("2人プレイ", True, (255, 255, 255))
    surface.blit(btn_2p_text, btn_2p_text.get_rect(center=btn_2p_rect.center))
    # トリセツ ボタン
    pygame.draw.rect(surface, (50, 50, 50), btn_manual_rect, border_radius=10)
    pygame.draw.rect(surface, (255, 255, 255),
                     btn_manual_rect, 3, border_radius=10)
    btn_manual_text = button_font.render("Instructions", True, (255, 255, 255))
    surface.blit(btn_manual_text, btn_manual_text.get_rect(
        center=btn_manual_rect.center))

def draw_manual_screen(surface, title_font, font, btn_back_rect):
    # トリセツ（操作説明）画面を描画 (HTMLを使用しない従来の形式)
  surface.fill((30, 30, 50))
  title_text = "トリセツとコマンド"
  title_width = title_font.size(title_text)[0]
  draw_text_border(surface, title_text, title_font, (255, 255, 255), (0, 0, 0),
                   surface.get_width() // 2 - title_width // 2, 50, 2)

  # 1P/2Pの操作説明を修正した内容
  instructions = [
      "--- シングルプレイモード ---",
      "移動: A (←), D (→)",
      "ジャンプ: W (↑)",
      "ズームアウト: R",
      "フロアマップの表示/非表示: M",
      "チャットボックスの表示/非表示: ~ (チルダ/バッククォート)",  # 修正
      "",
      "--- 2人プレイモード ---",
      "1P (画面左): WASD, ジャンプ: W, ズームアウト: R",
      "2P (画面右): 矢印キー (←↓→), ジャンプ: ↑, ズームアウト: . (ピリオド)",
      "",
      "--- Special Items ---",
      "Blue Pad: High Jump",
      "Green Pad: Super Jump (Highest)",
      "",
      "Climb high and reach the GOAL (Y: 30000) within 300 seconds!",
  ]
  y_start = 150
  for line in instructions:
    color = (255, 255, 0) if "---" in line else (255, 255, 255)
    text_render = font.render(line, True, color)
    text_rect = text_render.get_rect(
        centerx=surface.get_width() // 2, top=y_start)
    surface.blit(text_render, text_rect)
    y_start += 40

  # Back Button
  pygame.draw.rect(surface, (150, 50, 50), btn_back_rect, border_radius=10)
  pygame.draw.rect(surface, (255, 255, 255), btn_back_rect, 3, border_radius=10)
  btn_back_text = font.render("Back", True, (255, 255, 255))
  surface.blit(btn_back_text, btn_back_text.get_rect(
      center=btn_back_rect.center))

# --- オープニング画面 ---
def run_opening_screen(surface, image, duration_seconds=3):
    # オープニング画像を表示し、フェードアウトを行う
  if not image:
    return True

  elapsed = time.time() - main.opening_start_time

  # 画像を画面サイズに合わせる
  scaled_img = pygame.transform.scale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))
  surface.blit(scaled_img, (0, 0))

  # フェードアウト処理
  if elapsed > duration_seconds - 1.0:  # 最後の1秒でフェードアウト
    alpha = int(255 * (1.0 - (elapsed - (duration_seconds - 1.0))))
    alpha = max(0, alpha)
    fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    fade_surface.fill((0, 0, 0))
    fade_surface.set_alpha(alpha)
    surface.blit(fade_surface, (0, 0))
    return False  # 演出が続行中
  return True  # 演出完了


# --- ロード画面 ---
def run_loading_screen(surface, background_image, font):
    # ロード画面とアニメーションを表示する (文字演出強化済み)
  if not background_image:
    surface.fill((0, 0, 0))     # 背景画像がない場合は黒
  else:
      # 背景画像を画面サイズに合わせる
    scaled_bg = pygame.transform.scale(
        background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
    surface.blit(scaled_bg, (0, 0))

  # ローディングアニメーション（回転と一文字表示）
  loading_message = "LOADING..."
  anim_time = pygame.time.get_ticks() / 1000.0

  # 1. 文字全体を回転させる角度
  rotation_angle = (anim_time * 90) % 360     # 4秒で1周
  rotated_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
  rotated_surface.fill((0, 0, 0, 0))     # 透明なサーフェス

  # 2. 一文字ずつ表示 (だららら演出)
  CHAR_DISPLAY_SPEED = 0.5     # 1文字あたりの表示時間
  loop_duration = CHAR_DISPLAY_SPEED * len(loading_message)
  chars_to_show = int(((anim_time * 1.5) %
                      loop_duration) / CHAR_DISPLAY_SPEED) + 1
  chars_to_show = min(chars_to_show, len(loading_message))

  # 描画開始X座標を計算 (全体の幅と中央揃え)
  font_size = font.size(loading_message)
  total_width = font_size[0]
  start_x_on_rotated = (SCREEN_WIDTH // 2) - (total_width // 2)

  text_x = start_x_on_rotated
  text_y = SCREEN_HEIGHT // 2 - font_size[1] // 2     # 垂直中央

  for i, char in enumerate(loading_message):
    if i < chars_to_show:
      draw_text_border(rotated_surface, char, font, (255, 255, 255), (0, 0, 0),
                       text_x, text_y, 2)
      # 次の文字の開始X座標に更新
      char_render = font.render(char, True, (255, 255, 255))
      text_x += char_render.get_width()

  # 3. 回転と画面へのblit
  rotated_image = pygame.transform.rotate(rotated_surface, rotation_angle)
  rect = rotated_image.get_rect(
      center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
  surface.blit(rotated_image, rect)

  # ローディングアニメーション（右下）
  progress = (anim_time * 0.5) % 1.0     # 2秒で1周するアニメーション
  center_x = SCREEN_WIDTH - 50
  center_y = SCREEN_HEIGHT - 50
  radius = 20

  pygame.draw.circle(surface, (200, 200, 255),
                     (center_x, center_y), radius + 5, 2)

  start_angle = math.pi / 2     # 上から開始
  end_angle = start_angle - (2 * math.pi * progress)

  rect = pygame.Rect(center_x - radius, center_y -
                     radius, radius * 2, radius * 2)

  pygame.draw.arc(surface, (255, 255, 0), rect,
                  end_angle, start_angle, 5)  # 黄色の進捗


def draw_chat_box(surface, font, is_active, input_text, history):
    # チャットボックスを描画するヘルパー関数
  CHAT_WIDTH = 400
  CHAT_HEIGHT = 300
  PADDING = 10

  # ウィンドウの位置 (画面右下)
  box_rect = pygame.Rect(
      surface.get_width() - CHAT_WIDTH - PADDING,
      surface.get_height() - CHAT_HEIGHT - PADDING,
      CHAT_WIDTH, CHAT_HEIGHT
  )

  # 背景と枠線
  chat_surface = pygame.Surface((CHAT_WIDTH, CHAT_HEIGHT), pygame.SRCALPHA)
  chat_surface.fill((50, 50, 70, 200))  # 濃い背景 (半透明)
  pygame.draw.rect(chat_surface, (200, 200, 255),
                   chat_surface.get_rect(), 2, border_radius=5)  # 枠線
  surface.blit(chat_surface, box_rect.topleft)

  # 履歴表示エリアの矩形 (チャットボックス内の座標)
  # font.get_height() * 2 は、入力行とその上のスペースを確保するため
  history_area_height = CHAT_HEIGHT - PADDING * 2 - (font.get_height() * 2)
  # history_rect_internal = pygame.Rect(
  #     PADDING,
  #     PADDING,
  #     CHAT_WIDTH - PADDING * 2,
  #     history_area_height
  # )

  # 履歴の描画
  y_pos = CHAT_HEIGHT - PADDING - font.get_height() * 2  # 入力欄の上に開始
  line_height = font.get_height() + 5

  # 最新のメッセージから表示
  for msg in reversed(history):
    prefix = f"{'先生' if msg['sender'] == 'Teacher' else 'あなた'}: "
    color = (255, 255, 0) if msg['sender'] == 'Teacher' else (200, 255, 200)

    text_render = font.render(prefix + msg['text'], True, color)

    y_pos -= line_height

    # テキストが履歴エリアの上端を超えたら描画を停止 (PADDINGの高さから開始)
    if y_pos < PADDING:
      break

    # ボックスの左上隅からの絶対位置に描画
    surface.blit(text_render, (box_rect.left + PADDING, box_rect.top + y_pos))

  # 入力ボックス
  input_y_internal = CHAT_HEIGHT - PADDING - font.get_height()

  # 入力プロンプト
  prompt_text = font.render(
      "> " + input_text + ("|" if is_active else ""), True, (255, 255, 255))
  input_rect_internal = pygame.Rect(
      PADDING,
      input_y_internal - 2,
      CHAT_WIDTH - PADDING * 2,
      font.get_height() + 4
  )

  # 入力アクティブ時は入力背景を描画
  if is_active:
    input_rect_absolute = input_rect_internal.move(box_rect.topleft)
    pygame.draw.rect(surface, (100, 100, 120), input_rect_absolute)

  # 入力テキストをチャットボックス内に描画
  surface.blit(prompt_text, (box_rect.left +
               input_rect_internal.left + 5, box_rect.top + input_y_internal))

  # チャットボックスのヒント
  if not is_active:
    hint_text = "Press '~' to chat"  # 修正
  else:
    hint_text = "Enter: Send, Esc: Close"
  hint_render = font.render(hint_text, True, (150, 150, 150))
  surface.blit(hint_render, (box_rect.left + PADDING,
               box_rect.top - hint_render.get_height() - 5))


# --- メインゲームループ ---
def main():
    # ゲームの状態
  STATE_OPENING = 0      # オープニング画像表示 (キー入力待ち)
  STATE_SELECT_MODE = 1    # 1P/2P/説明書選択
  STATE_MANUAL = 11      # 説明書表示
  STATE_LOADING = 2      # ロード画面
  STATE_PLAYING = 3      # ゲームプレイ中
  STATE_GAME_OVER = 4      # ゲーム終了

  # --- 変数 ---
  play_mode = 0      # 1: 1P, 2: 2P
  player1 = None
  player2 = None
  camera1 = None
  camera2 = None
  current_zoom_p1 = 1.0
  current_zoom_p2 = 1.0
  show_overview_map = True

  # P1をWASD、P2を矢印キーに固定
  control_map_p1 = {'left': pygame.K_a, 'right': pygame.K_d,
                    'jump': pygame.K_w, 'zoom_out': pygame.K_r}
  control_map_p2 = {'left': pygame.K_LEFT, 'right': pygame.K_RIGHT,
                    'jump': pygame.K_UP, 'zoom_out': pygame.K_PERIOD}

  HALF_SCREEN_WIDTH = SCREEN_WIDTH // 2

  # 初期値としてFull/Split画面用のSubsurfaceを定義
  SCREEN_SURFACE_P1 = screen.subsurface(
      pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
  SCREEN_SURFACE_P2 = screen.subsurface(
      pygame.Rect(0, 0, 0, 0))  # 2Pモード以外では使用しない

  current_bgm = ""
  game_start_time = 0
  camera_smoothing = 0.15
  game_end_message = ""

  # 状態遷移変数
  loading_start_time = 0
  LOADING_DURATION = 3.0
  voice_played_after_loading = False     # ロード完了時の音声再生フラグ
  opening_show_duration = 3.0
  main.opening_start_time = time.time()  # グローバルな時間として設定
  is_opening_animation_done = False

  # モード選択画面のサブステート
  select_mode_substate = "MAIN_SELECT"

  # フォント設定 (グローバル変数を使用)
  global font, title_font, button_font

  # --- チャット関連変数 ---
  is_chat_active = False  # ~キーで表示されるチャットボックスがアクティブかどうか (初期値: False)
  chat_input_text = ""
  chat_history = []

  # 全体マップの位置を画面左上 (10, 10) に変更
  overview_rect = pygame.Rect(0, 0, overview_width, overview_height)
  overview_rect.topleft = (10, 10)

  # モード選択ボタンの矩形
  BTN_WIDTH = 250
  BTN_HEIGHT = 80
  center_x = SCREEN_WIDTH // 2
  center_y = SCREEN_HEIGHT // 2

  # ボタン位置の調整
  btn_1p_rect = pygame.Rect(center_x - BTN_WIDTH // 2,
                            center_y - BTN_HEIGHT * 1.5, BTN_WIDTH, BTN_HEIGHT)
  btn_2p_rect = pygame.Rect(center_x - BTN_WIDTH // 2,
                            center_y - BTN_HEIGHT * 0.5, BTN_WIDTH, BTN_HEIGHT)
  btn_manual_rect = pygame.Rect(
      center_x - BTN_WIDTH // 2, center_y + BTN_HEIGHT * 0.5, BTN_WIDTH, BTN_HEIGHT)

  # 戻るボタン (説明書画面用)
  BTN_BACK_WIDTH = 150
  BTN_BACK_HEIGHT = 50
  btn_back_rect = pygame.Rect(
      SCREEN_WIDTH // 2 - BTN_BACK_WIDTH // 2,
      SCREEN_HEIGHT - BTN_BACK_HEIGHT - 30,
      BTN_BACK_WIDTH, BTN_BACK_HEIGHT)

  # 初期ステート
  game_state = STATE_OPENING

  running = True
  while running:
    clock.tick(FPS)
    keys = pygame.key.get_pressed()

    # --- イベント処理 ---
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False

      if event.type == pygame.KEYDOWN:
        # プレイ中のキー操作
        if game_state == STATE_PLAYING:

          # ~キーでのチャットトグル処理
          if event.key == pygame.K_BACKQUOTE:  # ~または`キー
            is_chat_active = not is_chat_active
            if is_chat_active:
              chat_input_text = ""  # 入力リセット

          if is_chat_active:
            # チャットがアクティブのときのみ、テキスト入力と送信を処理
            if event.key == pygame.K_RETURN:
              if chat_input_text.strip():
                # プレイヤーメッセージを履歴に追加
                player_msg = chat_input_text.strip()
                chat_history.append(
                    {"sender": "Player", "text": player_msg, "time": time.time()})

                # --- 特殊応答チェック ---
                if "ダブルトーラス" in player_msg:
                  teacher_response = TORUS_RESPONSE
                else:
                  teacher_response = random.choice(TEACHER_MESSAGES)

                # 先生のメッセージを履歴に追加
                chat_history.append(
                    {"sender": "Teacher", "text": teacher_response, "time": time.time()})
                chat_input_text = ""  # 入力リセット

            elif event.key == pygame.K_BACKSPACE:
              chat_input_text = chat_input_text[:-1]
            elif event.key == pygame.K_ESCAPE:
              is_chat_active = False  # Escキーでチャットを閉じる

            # 文字入力イベント (KEYDOWNイベントにunicode属性がある場合)
            # IMEからの入力に対応するため、KEYDOWNで文字が送られてきた場合も捕捉
            elif event.unicode and event.key != pygame.K_BACKQUOTE:
                # 特殊キーや制御文字を除外してテキストに追加
                # スペースや通常の文字であれば追加
              if len(event.unicode) == 1:
                chat_input_text += event.unicode

          else:
            # チャットが非アクティブのときのみ、ゲーム内操作キーを処理
            if event.key == pygame.K_m:
              show_overview_map = not show_overview_map

        # オープニング後のキー待ち
        if game_state == STATE_OPENING and is_opening_animation_done:
          game_state = STATE_SELECT_MODE     # キーまたはクリックで遷移

      # モード選択画面のクリック処理
      if game_state == STATE_SELECT_MODE:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:  # 左クリック
          if btn_1p_rect.collidepoint(event.pos):
            play_mode = 1
            game_state = STATE_LOADING
            loading_start_time = time.time()
            voice_played_after_loading = False     # ロード毎にリセット
          elif btn_2p_rect.collidepoint(event.pos):
            play_mode = 2
            game_state = STATE_LOADING
            loading_start_time = time.time()
            voice_played_after_loading = False     # ロード毎にリセット
          elif btn_manual_rect.collidepoint(event.pos):
            game_state = STATE_MANUAL     # 説明書画面へ

      # 説明書画面のクリック処理
      elif game_state == STATE_MANUAL:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
          if btn_back_rect.collidepoint(event.pos):
            game_state = STATE_SELECT_MODE     # モード選択画面へ戻る

    # --- ゲームロジックと描画 ---
    if game_state == STATE_OPENING:
        # オープニングアニメーションを続行・描画
      screen.fill((0, 0, 0))
      if not is_opening_animation_done:
        is_opening_animation_done = (
            time.time() - main.opening_start_time) >= opening_show_duration

      if (time.time() - main.opening_start_time) < opening_show_duration:
          # アニメーション中
        run_opening_screen(screen, opening_image, opening_show_duration)
      else:
          # アニメーション終了後、キー待ち状態の描画
        if opening_image:
          scaled_img = pygame.transform.scale(
              opening_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
          screen.blit(scaled_img, (0, 0))

        # フェードアウト後の透明度調整 (キー待ち状態を示す)
        fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fade_surface.fill((0, 0, 0))
        fade_surface.set_alpha(150)     # 少し暗くする
        screen.blit(fade_surface, (0, 0))

        # キー入力待ちのメッセージ
        press_key_text = "Press any key or click to proceed"
        draw_text_border(screen, press_key_text, font, (255, 255, 255), (0, 0, 0),
                         SCREEN_WIDTH // 2 -
                         font.size(press_key_text)[0] // 2,
                         SCREEN_HEIGHT - 50, 2)

    elif game_state == STATE_SELECT_MODE:
      draw_select_mode_screen(
          screen, title_font, button_font, btn_1p_rect, btn_2p_rect, btn_manual_rect, "MAIN_SELECT")

    elif game_state == STATE_MANUAL:
      draw_manual_screen(screen, title_font, font, btn_back_rect)

    elif game_state == STATE_LOADING:
      run_loading_screen(screen, loading_background, title_font)

      # 音声再生の制御 (一度だけ再生)
      if not voice_played_after_loading and "areyouready" in voice_dict:
        try:
          if voice_dict["areyouready"].get_length() > 0:
            voice_dict["areyouready"].play()
        except Exception:
          voice_dict["areyouready"].play()
        voice_played_after_loading = True

      if time.time() - loading_start_time >= LOADING_DURATION:
          # ロード完了後の初期化処理
        game_start_time = time.time()
        current_bgm = switch_bgm("original", "")

        if play_mode == 1:
            # 1P 初期化
          player1 = Player(1, image_right, image_left,
                           2800.0, CHANNEL_P1_SFX, CHANNEL_P1_WIND)
          camera1 = Camera(CAMERA_WIDTH_1P, CAMERA_HEIGHT)
          # Fullscreen P1 screen surface
          SCREEN_SURFACE_P1 = screen.subsurface(
              pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

        elif play_mode == 2:
            # 2P 初期化
          player1 = Player(1, image_right, image_left,
                           2800.0, CHANNEL_P1_SFX, CHANNEL_P1_WIND)
          player2 = Player(2, image_right, image_left,
                           3200.0, CHANNEL_P2_SFX, CHANNEL_P2_WIND)
          camera1 = Camera(CAMERA_WIDTH_2P, CAMERA_HEIGHT)
          camera2 = Camera(CAMERA_WIDTH_2P, CAMERA_HEIGHT)
          # Split screen surfaces
          SCREEN_SURFACE_P1 = screen.subsurface(
              pygame.Rect(0, 0, HALF_SCREEN_WIDTH, SCREEN_HEIGHT))
          SCREEN_SURFACE_P2 = screen.subsurface(pygame.Rect(
              HALF_SCREEN_WIDTH, 0, HALF_SCREEN_WIDTH, SCREEN_HEIGHT))

        game_state = STATE_PLAYING

    elif game_state == STATE_PLAYING:
        # --- 時間の計算 --- (チャットアクティブ/非アクティブに関わらず進行)
      current_time = time.time()
      elapsed_time = current_time - game_start_time
      remaining_time = max(0, TIME_LIMIT - elapsed_time)
      timer_text = f"TIME: {int(remaining_time):03d}s"

      # チャットがアクティブでない場合のみプレイヤーを更新
      if not is_chat_active:
        # --- プレイヤー更新 (モードに基づく) ---
        if play_mode == 1 and player1 and camera1:
          player1.update(keys, control_map_p1)
          highest_y = player1.y
        elif play_mode == 2 and player1 and player2 and camera1 and camera2:
          player1.update(keys, control_map_p1)
          player2.update(keys, control_map_p2)
          highest_y = max(player1.y, player2.y)
        else:
          highest_y = 0

        # BGM 切り替え
        if highest_y < 9500:
          current_bgm = switch_bgm("original", current_bgm)
        elif highest_y < 25000:
          current_bgm = switch_bgm("mid", current_bgm)
        else:
          current_bgm = switch_bgm("high", current_bgm)

        # ズームとカメラ更新
        if player1 and camera1:
          target_zoom_p1 = ZOOM_OUT_SCALE if player1.is_zooming_out else 1.0
          current_zoom_p1 += (target_zoom_p1 - current_zoom_p1) * ZOOM_SMOOTHING
          camera1.update(player1, camera_smoothing, current_zoom_p1)

        if play_mode == 2 and player2 and camera2:
          target_zoom_p2 = ZOOM_OUT_SCALE if player2.is_zooming_out else 1.0
          current_zoom_p2 += (target_zoom_p2 - current_zoom_p2) * ZOOM_SMOOTHING
          camera2.update(player2, camera_smoothing, current_zoom_p2)

      # --- ゲームオーバー判定 ---
      game_over = False
      if remaining_time <= 0:
        game_over = True
        game_end_message = "TIME OVER!"
      elif play_mode == 1 and player1 and player1.is_goal:
        game_over = True
        game_end_message = "GOAL! YOU MADE IT!"
      elif play_mode == 2 and (player1 or player2):
        if (player1 and player1.is_goal) or (player2 and player2.is_goal):
          game_over = True
          if player1 and player1.is_goal and player2 and player2.is_goal:
            game_end_message = "DRAW! Both players reached the goal!"
          elif player1 and player1.is_goal:
            game_end_message = "1P WINS! (Goal Reached)"
          else:
            game_end_message = "2P WINS! (Goal Reached)"

      if game_over:
        game_state = STATE_GAME_OVER
        pygame.mixer.music.stop()

      # --- 描画 ---
      screen.fill((0, 0, 0))

      # タイマー描画の準備
      timer_text_render = font.render(timer_text, True, (255, 0, 0))
      timer_rect = timer_text_render.get_rect()

      if play_mode == 1 and player1 and camera1:
          # 1P ゲームビューを描画 (フルスクリーン)
        draw_game_view(screen, player1, camera1, CAMERA_WIDTH_1P,
                       CAMERA_HEIGHT, current_zoom_p1, None, font)

        # タイマーを描画 (フルスクリーンの右上)
        timer_rect.topright = (SCREEN_WIDTH - 10, 50)
        screen.blit(timer_text_render, timer_rect)

        # 全体マップを描画 (左上に設定した overview_rect を使用)
        if show_overview_map:
          # 1Pモードでは overview_rect の位置をそのまま使用 (左上)
          draw_overview_map(screen, player1, None, overview_width,
                            overview_height, MAP_WIDTH, MAP_HEIGHT, font, overview_rect)

      elif play_mode == 2 and player1 and player2 and camera1 and camera2:
          # 1P ゲームビューを描画 (左側)
        draw_game_view(SCREEN_SURFACE_P1, player1, camera1,
                       CAMERA_WIDTH_2P, CAMERA_HEIGHT, current_zoom_p1, "1P", font)

        # 2P ゲームビューを描画 (右側)
        draw_game_view(SCREEN_SURFACE_P2, player2, camera2,
                       CAMERA_WIDTH_2P, CAMERA_HEIGHT, current_zoom_p2, "2P", font)

        # 中央に区切り線を描画 (色を黒に変更)
        pygame.draw.line(screen, (0, 0, 0),
                         (HALF_SCREEN_WIDTH, 0), (HALF_SCREEN_WIDTH, SCREEN_HEIGHT), 3)

        # タイマーを描画 (中央上部)
        timer_rect.centerx = SCREEN_WIDTH // 2
        timer_rect.top = 10
        draw_text_border(screen, timer_text, font, (255, 0, 0), (0, 0, 0),
                         timer_rect.left, timer_rect.top, 2)

        # 全体マップを描画 (P1画面の左上に表示)
        if show_overview_map:
          # P1画面用の概要マップ矩形 (左画面の左上)
          # overview_rectは既に(10, 10)になっているため、これをそのまま使用
          draw_overview_map(screen, player1, player2, overview_width,
                            overview_height, MAP_WIDTH, MAP_HEIGHT, font, overview_rect)

      # --- Chat Boxの描画 (ゲーム画面の上に重ねて描画) ---
      if is_chat_active or (game_state == STATE_PLAYING and not is_chat_active):
          # is_chat_activeがTrueの時、またはプレイ中にヒントのために常に描画
        draw_chat_box(screen, font, is_chat_active,
                      chat_input_text, chat_history)

    elif game_state == STATE_GAME_OVER:
      draw_end_screen(screen, game_end_message, title_font)
      running = False

    pygame.display.flip()


if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    print(f"An unexpected error occurred: {e}")
  finally:
    pygame.quit()
    sys.exit()
