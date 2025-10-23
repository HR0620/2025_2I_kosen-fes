import pygame
import sys
import math
import time

pygame.init()
pygame.mixer.init()

# --- 定数設定 ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60
CAMERA_WIDTH = 375
CAMERA_HEIGHT = 400
TIME_LIMIT = 300  # 制限時間 (秒)
GOAL_Y = 30000.0  # ゴールとなるマップのY座標 (下から30,000ピクセル)
ZOOM_OUT_SCALE = 0.7  # ズームアウト時の目標倍率 (1.0が標準)
ZOOM_SMOOTHING = 0.1  # ズーム率変更の滑らかさ

PNG_PATH = "./png/"
BGM_PATH = "./mp3/bgm/"
EFFECT_PATH = "./mp3/effect/"
VOICE_PATH = "./mp3/voice/"

# --- ゲーム画面初期化 ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("OnlyUp風ゲーム (2P Split Screen)")
clock = pygame.time.Clock()

# --- マップ画像読み込み ---
try:
  map_image = pygame.image.load(f"{PNG_PATH}map_highres.png").convert_alpha()
except pygame.error as e:
  print(f"Error loading map_highres.png: {e}. Please ensure the file exists.")
  pygame.quit()
  sys.exit()

MAP_WIDTH, MAP_HEIGHT = map_image.get_size()

# --- サウンド設定とチャンネル分け ---
try:
  jump_sound = pygame.mixer.Sound(f"{EFFECT_PATH}キックの素振り3.mp3")
  blue_sound = pygame.mixer.Sound(f"{EFFECT_PATH}ボヨン.mp3")
  green_sound = pygame.mixer.Sound(f"{EFFECT_PATH}爆発1.mp3")
  fall_sound = pygame.mixer.Sound(f"{EFFECT_PATH}ジャンプの着地.mp3")
  wind_sound = pygame.mixer.Sound(f"{EFFECT_PATH}Wind-Synthetic_Ambi01-1.mp3")
except pygame.error as e:
  print(
      f"Error loading sound files. Check file paths and formats: {e}. Some sounds may not play.")

# チャンネル割り当て (SFXと風の音用)
CHANNEL_P1_SFX = pygame.mixer.Channel(0)
CHANNEL_P2_SFX = pygame.mixer.Channel(1)
CHANNEL_P1_WIND = pygame.mixer.Channel(2)
CHANNEL_P2_WIND = pygame.mixer.Channel(3)

# 風の音をループ再生開始 (初期音量は0.0)
CHANNEL_P1_WIND.play(wind_sound, loops=-1)
CHANNEL_P2_WIND.play(wind_sound, loops=-1)
CHANNEL_P1_WIND.set_volume(0.0)
CHANNEL_P2_WIND.set_volume(0.0)

# --- 自機画像読み込み & 縮小 ---
try:
  original_image = pygame.image.load(f"{PNG_PATH}muroya.png").convert_alpha()
except pygame.error as e:
  print(f"Error loading muroya.png: {e}. Please ensure the file exists.")
  pygame.quit()
  sys.exit()

scaled_image = pygame.transform.scale(original_image, (100, 150))
image_right = scaled_image
image_left = pygame.transform.flip(scaled_image, True, False)

# 1/20 縮小のマップ（画面に常に表示する用）
overview_width = 120
overview_height = int(MAP_HEIGHT * (overview_width / MAP_WIDTH))
map_overview = pygame.transform.scale(
    map_image, (overview_width, overview_height))

# --- プレイヤークラス ---
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
    self.image_right = image_right
    self.image_left = image_left

    self.sfx_channel = sfx_channel
    self.wind_channel = wind_channel
    self.is_zooming_out = False

  def play_sound(self, sound):
    self.sfx_channel.play(sound)

  def update(self, keys, control_map):
    if self.is_goal: return

    self.is_zooming_out = keys[control_map['zoom_out']]

    accel = 0.375 if self.on_ground else 0.025
    max_speed = self.speed

    if self.vy < -1.0:
      speed_factor = min(abs(self.vy) / 10, 1.0)
      self.wind_channel.set_volume(speed_factor * 0.8)
    else:
      self.wind_channel.set_volume(0.0)

    # 🌟 プレイヤーの向きロジック (ムーンウォーク状態)を維持 🌟
    if keys[control_map['left']]:
      self.vx -= accel
      self.facing_right = True  # 左移動で右向き
    elif keys[control_map['right']]:
      self.vx += accel
      self.facing_right = False  # 右移動で左向き
    else:
      if self.vx > 0:
        self.vx = max(0, self.vx - accel)
      elif self.vx < 0:
        self.vx = min(0, self.vx + accel)

    self.vx = max(-max_speed, min(self.vx, max_speed))

    if keys[control_map['jump']]:
      if self.on_ground:
        self.vy = self.jump_speed
        self.on_ground = False
        self.play_sound(jump_sound)
      elif self.wall_jump_cooldown == 0:
        if self.check_collision(self.x - 0.2, self.y) or self.check_collision(self.x + 0.2, self.y):
          self.vy = self.jump_speed * 0.8
          if self.check_collision(self.x - 0.2, self.y):
            self.vx = self.speed * 0.7
          else:
            self.vx = -self.speed * 0.7
          self.wall_jump_cooldown = 10
          self.play_sound(jump_sound)

    if self.wall_jump_cooldown > 0:
      self.wall_jump_cooldown -= 1

    self.vy -= self.gravity
    new_x = self.x + self.vx
    new_y = self.y + self.vy

    if not self.check_collision(new_x, self.y):
      self.x = new_x
    else:
      self.vx = 0

    if not self.check_collision(self.x, new_y):
      self.y = new_y
      self.on_ground = False
    else:
      if self.vy < 0:
        if not self.on_ground:
          self.play_sound(fall_sound)
        self.on_ground = True
      self.vy = 0

    self.x = max(0, min(self.x, MAP_WIDTH - self.width))
    self.y = max(0, self.y)

    if self.y >= GOAL_Y:
      self.is_goal = True
      self.vy = 0
      self.vx = 0

    special = self.check_special_jump()
    if special == 'blue':
      self.vy = 8.66
      self.play_sound(blue_sound)
    elif special == 'green':
      self.vy = 17.32
      self.play_sound(green_sound)

  def check_collision(self, x, y):
    left = int(x)
    right = int(math.ceil(x + self.width))
    bottom = int(y)
    top = int(math.ceil(y + self.height))

    for px in range(left, right):
      for py in range(bottom, top):
        if 0 <= px < MAP_WIDTH and 0 <= py < MAP_HEIGHT:
          img_y = MAP_HEIGHT - py - 1
          r, g, b, a = map_image.get_at((px, img_y))
          if r < 10 and g < 10 and b < 10 and a > 0:
            return True
    return False

  def draw(self, surface, cam_x, cam_y, screen_width, screen_height, camera_width, camera_height, zoom):
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
    left = int(self.x)
    right = int(math.ceil(self.x + self.width))
    bottom = int(self.y)
    top = int(math.ceil(self.y + self.height))

    for px in range(left, right):
      for py in range(bottom, top):
        if 0 <= px < MAP_WIDTH and 0 <= py < MAP_HEIGHT:
          img_y = MAP_HEIGHT - py - 1
          r, g, b, a = map_image.get_at((px, img_y))
          if r == 0 and g == 0 and b == 255:
            return 'blue'
          elif r == 0 and g == 255 and b == 0:
            return 'green'
    return None

# --- カメラクラス ---
class Camera:
  def __init__(self, camera_width, camera_height):
    self.x = 0
    self.y = 0
    self.CAMERA_WIDTH = camera_width
    self.CAMERA_HEIGHT = camera_height

  def update(self, player, smoothing, zoom_scale):
    target_display_width = self.CAMERA_WIDTH / zoom_scale
    target_display_height = self.CAMERA_HEIGHT / zoom_scale

    target_x = player.x + player.width / 2 - target_display_width / 2
    target_y = player.y + player.height / 2 - target_display_height / 2

    target_x = max(0, min(target_x, MAP_WIDTH - target_display_width))
    target_y = max(0, min(target_y, MAP_HEIGHT - target_display_height))

    self.x += (target_x - self.x) * smoothing
    self.y += (target_y - self.y) * smoothing


# --- 関数群 ---

def draw_text_border(surface, text, font, color, border_color, x, y, border_size=1):
  """袋文字を描画するヘルパー関数"""

  # 縁取りを描画 (外側)
  for dx in range(-border_size, border_size + 1):
    for dy in range(-border_size, border_size + 1):
      if dx != 0 or dy != 0:
        border_surface = font.render(text, True, border_color)
        surface.blit(border_surface, (x + dx, y + dy))

  # 本体を描画 (内側)
  text_surface = font.render(text, True, color)
  surface.blit(text_surface, (x, y))


def switch_bgm(target, current_bgm):
  """BGMを共通で切り替える (pygame.mixer.musicを使用)"""
  if target != current_bgm:
    print(f"[BGM] Switching to: {target}")
    try:
      if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

      # BGMファイル名が正しい前提
      if target == "original":
        pygame.mixer.music.load(f"{BGM_PATH}The Dark Eternal Night.mp3")
      elif target == "mid":
        pygame.mixer.music.load(f"{BGM_PATH}zanzou no hiyu.mp3")
      elif target == "high":
        pygame.mixer.music.load(f"{BGM_PATH}Outer Space.mp3")

      pygame.mixer.music.play(-1, fade_ms=2000)
      return target
    except Exception as e:
      print(f"[ERROR] Failed to load/play BGM: {e}")
      return current_bgm
  return current_bgm

def draw_overview_map(main_surface, player1, player2, camera2, ow_width, ow_height, map_w, map_h, font, overview_rect):
  """全体マップ（オーバービュー）を描画するヘルパー関数"""

  overview_surface = pygame.Surface(
      (ow_width, ow_height), pygame.SRCALPHA)
  overview_surface.set_alpha(200)

  overview_surface.blit(map_overview, (0, 0))
  main_surface.blit(overview_surface, overview_rect)

  pygame.draw.rect(main_surface, (255, 255, 255), overview_rect, 2)

  scale_x = ow_width / map_w
  scale_y = ow_height / map_h

  PLAYER_DOT_RADIUS = 4
  PLAYER_BORDER_RADIUS = 6
  BORDER_COLOR = (255, 215, 0)  # 金色

  # --- 1Pの位置を赤色 (外枠: 金色)で表示 ---
  player1_dot_x = int(player1.x * scale_x)
  player1_dot_y = int((map_h - player1.y) * scale_y)
  dot_pos1 = (overview_rect.left + player1_dot_x,
              overview_rect.top + player1_dot_y)

  pygame.draw.circle(main_surface, BORDER_COLOR,
                     dot_pos1, PLAYER_BORDER_RADIUS)
  pygame.draw.circle(main_surface, (255, 0, 0), dot_pos1,
                     PLAYER_DOT_RADIUS)  # 赤色 (1P)

  # --- 2Pの位置を青色 (外枠: 金色)で表示 ---
  player2_dot_x = int(player2.x * scale_x)
  player2_dot_y = int((map_h - player2.y) * scale_y)
  dot_pos2 = (overview_rect.left + player2_dot_x,
              overview_rect.top + player2_dot_y)
  pygame.draw.circle(main_surface, BORDER_COLOR,
                     dot_pos2, PLAYER_BORDER_RADIUS)
  pygame.draw.circle(main_surface, (0, 0, 255), dot_pos2,
                     PLAYER_DOT_RADIUS)  # 青色 (2P)
  # ゴールラインを描画
  goal_y_on_map = map_h - GOAL_Y
  goal_line_y = int(goal_y_on_map * scale_y)

  line_y_pos = overview_rect.top + goal_line_y

  if overview_rect.top < line_y_pos < overview_rect.bottom:
    pygame.draw.line(main_surface, (255, 255, 0),
                     (overview_rect.left, line_y_pos),
                     (overview_rect.right, line_y_pos), 2)

    text_goal = font.render("GOAL", True, (255, 255, 0))
    main_surface.blit(text_goal, (overview_rect.left,
                                  line_y_pos - text_goal.get_height() - 2))


def draw_game_view(surface, player, camera, cam_width, cam_height, zoom_scale, player_label, font, time_text=None):
  """個別のゲーム画面を描画するヘルパー関数"""

  display_width = cam_width / zoom_scale
  display_height = cam_height / zoom_scale

  rect_x = int(camera.x)
  rect_y = MAP_HEIGHT - int(camera.y) - display_height

  camera_rect = pygame.Rect(rect_x, rect_y, display_width, display_height)
  camera_rect.clamp_ip(pygame.Rect(0, 0, MAP_WIDTH, MAP_HEIGHT))

  sub_map = map_image.subsurface(camera_rect)

  scaled_map = pygame.transform.scale(
      sub_map, (surface.get_width(), surface.get_height()))
  surface.blit(scaled_map, (0, 0))

  player.draw(surface, camera.x, camera.y,
              surface.get_width(), surface.get_height(), display_width, display_height, zoom_scale)

  # プレイヤーラベルを袋文字で表示
  player_id_color = (255, 0, 0) if player.player_id == 1 else (0, 0, 255)

  draw_text_border(surface, player_label, font, player_id_color,
                   (255, 255, 255), 10, 10, border_size=2)

  # 🌟 修正: プレイヤー座標を整数のみで表示 🌟
  text_pos = font.render(
      f"Pos: ({int(player.x)}, {int(player.y)})", True, (255, 255, 255))
  surface.blit(text_pos, (surface.get_width() -
                          text_pos.get_width() - 10, 10))

  # 1P画面の右上に赤色でタイマーを表示
  if time_text and player.player_id == 1:
    timer_text_render = font.render(time_text, True, (255, 0, 0))
    surface.blit(timer_text_render, (surface.get_width() -
                                     timer_text_render.get_width() - 10, 50))


def draw_end_screen(surface, message, font):
  """ゲーム終了画面を描画する"""
  surface.fill((0, 0, 0))
  text_render = font.render(message, True, (255, 255, 255))
  rect = text_render.get_rect(
      center=(surface.get_width() // 2, surface.get_height() // 2))
  surface.blit(text_render, rect)
  pygame.display.flip()
  time.sleep(3)

# --- メイン ---
def main():

  player1 = Player(1, image_right, image_left, 2800.0,
                   CHANNEL_P1_SFX, CHANNEL_P1_WIND)
  player2 = Player(2, image_right, image_left, 3200.0,
                   CHANNEL_P2_SFX, CHANNEL_P2_WIND)
  camera1 = Camera(CAMERA_WIDTH, CAMERA_HEIGHT)
  camera2 = Camera(CAMERA_WIDTH, CAMERA_HEIGHT)

  current_zoom_p1 = 1.0
  current_zoom_p2 = 1.0

  # フロアマップ表示フラグ (初期値: True)
  show_overview_map = True

  control_map_p1 = {
      'left': pygame.K_a, 'right': pygame.K_d, 'jump': pygame.K_w, 'zoom_out': pygame.K_r
  }
  control_map_p2 = {
      'left': pygame.K_LEFT, 'right': pygame.K_RIGHT, 'jump': pygame.K_UP, 'zoom_out': pygame.K_PERIOD
  }

  HALF_SCREEN_WIDTH = SCREEN_WIDTH // 2
  SCREEN_SURFACE_P1 = screen.subsurface(
      pygame.Rect(0, 0, HALF_SCREEN_WIDTH, SCREEN_HEIGHT))
  SCREEN_SURFACE_P2 = screen.subsurface(pygame.Rect(
      HALF_SCREEN_WIDTH, 0, HALF_SCREEN_WIDTH, SCREEN_HEIGHT))

  current_bgm = ""
  current_bgm = switch_bgm("original", current_bgm)

  running = True
  game_over = False
  game_start_time = time.time()
  camera_smoothing = 0.15

  font = pygame.font.SysFont(None, 36)

  # フロアマップの位置を右上に設定
  overview_rect = pygame.Rect(0, 0, overview_width, overview_height)
  overview_rect.topright = (SCREEN_WIDTH - 10, 10)

  while running:
    clock.tick(FPS)

    current_time = time.time()
    elapsed_time = current_time - game_start_time
    remaining_time = max(0, TIME_LIMIT - elapsed_time)
    timer_text = f"TIME: {int(remaining_time):03d}s"

    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False

      # Mキーでフロアマップの表示/非表示を切り替え
      if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_m:
          show_overview_map = not show_overview_map

    if not game_over:
      # --- 更新処理 ---
      player1.update(keys, control_map_p1)
      player2.update(keys, control_map_p2)

      # BGM切り替え判定
      highest_y = max(player1.y, player2.y)
      if highest_y < 9500:
        current_bgm = switch_bgm("original", current_bgm)
      elif highest_y < 25000:
        current_bgm = switch_bgm("mid", current_bgm)
      else:
        current_bgm = switch_bgm("high", current_bgm)

      # スムーズなズーム率の計算
      target_zoom_p1 = ZOOM_OUT_SCALE if player1.is_zooming_out else 1.0
      current_zoom_p1 += (target_zoom_p1 -
                          current_zoom_p1) * ZOOM_SMOOTHING

      target_zoom_p2 = ZOOM_OUT_SCALE if player2.is_zooming_out else 1.0
      current_zoom_p2 += (target_zoom_p2 -
                          current_zoom_p2) * ZOOM_SMOOTHING

      # カメラ位置の更新
      camera1.update(player1, camera_smoothing, current_zoom_p1)
      camera2.update(player2, camera_smoothing, current_zoom_p2)

      # --- ゲーム終了判定 ---
      if remaining_time <= 0:
        game_over = True
        game_end_message = "TIME OVER! No one reached the goal."
        pygame.mixer.music.stop()
      elif player1.is_goal or player2.is_goal:
        game_over = True
        if player1.is_goal and player2.is_goal:
          game_end_message = "DRAW! Both players reached the goal!"
        elif player1.is_goal:
          game_end_message = "1P WINS! (Goal Reached)"
        else:
          game_end_message = "2P WINS! (Goal Reached)"
        pygame.mixer.music.stop()

      # --- 描画処理 ---
      screen.fill((0, 0, 0))

      # 1P 画面の描画
      draw_game_view(SCREEN_SURFACE_P1, player1, camera1, CAMERA_WIDTH,
                     CAMERA_HEIGHT, current_zoom_p1, "1P", font, timer_text)

      # 2P 画面の描画
      draw_game_view(SCREEN_SURFACE_P2, player2, camera2,
                     CAMERA_WIDTH, CAMERA_HEIGHT, current_zoom_p2, "2P", font)

      # 分割線を描画
      pygame.draw.line(screen, (0, 0, 0), (HALF_SCREEN_WIDTH, 0),
                       (HALF_SCREEN_WIDTH, SCREEN_HEIGHT), 3)

      # フロアマップ表示フラグに応じて描画
      if show_overview_map:
        draw_overview_map(screen, player1, player2, camera2,
                          overview_width, overview_height, MAP_WIDTH, MAP_HEIGHT, font, overview_rect)

    else:
      # ゲーム終了後の処理
      draw_end_screen(screen, game_end_message, font)
      running = False

    pygame.display.flip()

  pygame.quit()
  sys.exit()


if __name__ == "__main__":
  main()
