import pygame
import sys
import math

pygame.init()
pygame.mixer.init()


# --- 画面サイズ・FPS ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60

# --- 表示カメラの大きさ（マップピクセル単位） ---
CAMERA_WIDTH = 750
CAMERA_HEIGHT = 400

# --- ゲーム画面初期化（convert_alpha前に必要） ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("OnlyUp風ゲーム")
clock = pygame.time.Clock()

# --- マップ画像読み込み ---
map_image = pygame.image.load("map_highres.png").convert_alpha()
MAP_WIDTH, MAP_HEIGHT = map_image.get_size()  # 6000 x 30000

jump_sound = pygame.mixer.Sound("キックの素振り3.mp3")
blue_sound = pygame.mixer.Sound("ボヨン.mp3")
green_sound = pygame.mixer.Sound("爆発1.mp3")
fall_sound = pygame.mixer.Sound("ジャンプの着地.mp3")
# プレイヤークラスの外、最初に一度だけロード
wind_sound = pygame.mixer.Sound("Wind-Synthetic_Ambi01-1.mp3")
wind_channel = pygame.mixer.Channel(1)
wind_channel.play(wind_sound, loops=-1)
wind_channel.set_volume(0.0)

# 自機画像読み込み & 縮小
original_image = pygame.image.load("muroya.png").convert_alpha()

# 表示サイズに合わせて縮小（ここでは 20x30 に合わせる）
scaled_image = pygame.transform.scale(original_image, (100, 150))
image_right = scaled_image
image_left = pygame.transform.flip(scaled_image, True, False)

# 1/20 縮小のマップ（画面に常に表示する用）
overview_width = 120
overview_height = int(MAP_HEIGHT * (overview_width / MAP_WIDTH))  # 高さも比率で自動調整

map_overview = pygame.transform.scale(
    map_image, (overview_width, overview_height))


# --- プレイヤークラス ---
class Player:
  def __init__(self, image_right, image_left):
    self.x = 2800.0
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

    # 向きと画像
    self.facing_right = True
    self.image_right = image_right
    self.image_left = image_left

  def update(self, keys):
    # 加速度（地上と空中で違う）
    accel = 0.375 if self.on_ground else 0.025
    max_speed = self.speed

    # Player.update() の中、重力処理のあとくらいに追加
    if self.vy < -1.0:  # 落下速度が速いとき
      speed_factor = min(abs(self.vy) / 10, 1.0)  # 0.0〜1.0 に正規化
      wind_channel.set_volume(speed_factor * 0.8)  # 最大音量 80%
    else:
      wind_channel.set_volume(0.0)

    # 左右加減速
    if keys[pygame.K_LEFT]:
      self.vx -= accel
      self.facing_right = True
    elif keys[pygame.K_RIGHT]:
      self.vx += accel
      self.facing_right = False

    else:
      if self.vx > 0:
        self.vx = max(0, self.vx - accel)
      elif self.vx < 0:
        self.vx = min(0, self.vx + accel)

    # 最大速度制限
    self.vx = max(-max_speed, min(self.vx, max_speed))

    # ジャンプと壁キック
    if keys[pygame.K_SPACE] or keys[pygame.K_UP]:
      if self.on_ground:
        self.vy = self.jump_speed
        self.on_ground = False
        jump_sound.play()
      elif self.wall_jump_cooldown == 0:
        # 左の壁
        if self.check_collision(self.x - 0.2, self.y):
          self.vy = self.jump_speed * 0.8
          self.vx = self.speed * 0.7
          self.wall_jump_cooldown = 10
          jump_sound.play()
        # 右の壁
        elif self.check_collision(self.x + 0.2, self.y):
          self.vy = self.jump_speed * 0.8
          self.vx = -self.speed * 0.7
          self.wall_jump_cooldown = 10
          jump_sound.play()

    if self.wall_jump_cooldown > 0:
      self.wall_jump_cooldown -= 1

    # 重力
    self.vy -= self.gravity

    # 移動候補
    new_x = self.x + self.vx
    new_y = self.y + self.vy

    # 横方向の当たり判定
    if not self.check_collision(new_x, self.y):
      self.x = new_x
    else:
      self.vx = 0

    # 縦方向の当たり判定
    if not self.check_collision(self.x, new_y):
      self.y = new_y
      self.on_ground = False
    else:
      if self.vy < 0:
        self.on_ground = True
      self.vy = 0

    # 範囲外制限
    self.x = max(0, min(self.x, MAP_WIDTH - self.width))
    self.y = max(0, self.y)

    # --- 特殊ジャンプ（色による）
    special = self.check_special_jump()
    if special == 'blue':
      self.vy = 8.66  # 青ブロック（500pxジャンプ）
      blue_sound.play()
    elif special == 'green':
      self.vy = 17.32  # 緑ブロック（2000pxジャンプ）
      green_sound.play()

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

  def draw(self, surface, cam_x, cam_y, zoom=1.0):
    scale_x = (SCREEN_WIDTH / CAMERA_WIDTH) * zoom
    scale_y = (SCREEN_HEIGHT / CAMERA_HEIGHT) * zoom
    screen_x = (self.x - cam_x) * scale_x
    screen_y = SCREEN_HEIGHT - \
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

class Camera:
  def __init__(self):
    self.x = 0
    self.y = 0

  def update(self, player):
    target_x = player.x + player.width / 2 - CAMERA_WIDTH / 2
    target_y = player.y + player.height / 2 - CAMERA_HEIGHT / 2

    target_x = max(0, min(target_x, MAP_WIDTH - CAMERA_WIDTH))
    target_y = max(0, min(target_y, MAP_HEIGHT - CAMERA_HEIGHT))

    smoothing = 0.1  # 追従速度（小さいほど遅くなる）
    self.x += (target_x - self.x) * smoothing
    self.y += (target_y - self.y) * smoothing

def switch_bgm(target, current_bgm):
  if target != current_bgm or not pygame.mixer.music.get_busy():
    print(f"[BGM] Switching to: {target}")
    try:
      if target == "original":
        pygame.mixer.music.load("The Dark Eternal Night.mp3")
      elif target == "mid":
        pygame.mixer.music.load("zanzou no hiyu.mp3")
      elif target == "high":
        pygame.mixer.music.load("Outer Space.mp3")

      pygame.mixer.music.play(-1, fade_ms=2000)
    except Exception as e:
      print(f"[ERROR] Failed to load/play BGM: {e}")
      return current_bgm

    if pygame.mixer.music.get_busy():
      print(f"[BGM] Now playing: {target}")
    else:
      print("[ERROR] BGM is not playing")

    return target

  return current_bgm


# --- メイン ---
def main():
  pygame.init()
  pygame.mixer.init()
  player = Player(image_right, image_left)
  player.y = 200
  current_bgm = "original"
  current_bgm = switch_bgm("original", current_bgm)
  running = True
  camera = Camera()

  dragging = False
  drag_start_pos = (0, 0)
  camera_start_pos = (0, 0)
  camera_target_x = 0
  camera_target_y = 0
  clicked_map_pos = None

  follow_enabled = False

  smoothing = 0.15  # 補間の速さ（0.0〜1.0）

  while running:
    clock.tick(FPS)
    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False

      elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        dragging = True
        drag_start_pos = event.pos
        camera_start_pos = (camera.x, camera.y)
        follow_enabled = False  # 追従カメラ停止

      elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        dragging = False
        mouse_x, mouse_y = event.pos
        cam_rel_x = mouse_x / (SCREEN_WIDTH / CAMERA_WIDTH)
        cam_rel_y = (SCREEN_HEIGHT - mouse_y) / (SCREEN_HEIGHT / CAMERA_HEIGHT)
        map_x = camera.x + cam_rel_x
        map_y = camera.y + cam_rel_y
        clicked_map_pos = (map_x, map_y)

    if any(keys):
      follow_enabled = True

    player.update(keys)

    # BGM切り替え判定
    if player.y < 9500:
      current_bgm = switch_bgm("original", current_bgm)
    elif player.y < 25000:
      current_bgm = switch_bgm("mid", current_bgm)
    else:
      current_bgm = switch_bgm("high", current_bgm)

    if follow_enabled:
      # 追従カメラ目標座標に設定
      camera_target_x = player.x + player.width / 2 - CAMERA_WIDTH / 2
      camera_target_y = player.y + player.height / 2 - CAMERA_HEIGHT / 2

      camera_target_x = max(0, min(camera_target_x, MAP_WIDTH - CAMERA_WIDTH))
      camera_target_y = max(0, min(camera_target_y, MAP_HEIGHT - CAMERA_HEIGHT))

    else:
      if dragging:
        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = (drag_start_pos[0] - mouse_x) / (SCREEN_WIDTH / CAMERA_WIDTH)
        dy = (mouse_y - drag_start_pos[1]) / (SCREEN_HEIGHT / CAMERA_HEIGHT)
        camera_target_x = camera_start_pos[0] + dx
        camera_target_y = camera_start_pos[1] + dy

        camera_target_x = max(0, min(camera_target_x, MAP_WIDTH - CAMERA_WIDTH))
        camera_target_y = max(
            0, min(camera_target_y, MAP_HEIGHT - CAMERA_HEIGHT))

    # カメラ位置を滑らかに更新
    camera.x += (camera_target_x - camera.x) * smoothing
    camera.y += (camera_target_y - camera.y) * smoothing

    # メインループ内、描画前あたりに追加
    if dragging:
      zoom_scale = 0.8  # 80%にズームアウト
    else:
      zoom_scale = 1.0  # 通常倍率

    # 表示部分の切り出しサイズを倍率で調整
    display_width = int(SCREEN_WIDTH / zoom_scale)
    display_height = int(SCREEN_HEIGHT / zoom_scale)

    rect_x = max(0, min(int(camera.x), MAP_WIDTH - display_width))
    rect_y = max(0, min(MAP_HEIGHT - int(camera.y) -
                 display_height, MAP_HEIGHT - display_height))

    camera_rect = pygame.Rect(rect_x, rect_y, display_width, display_height)

    sub_map = map_image.subsurface(camera_rect)

    # スケールして画面全体に表示
    scaled_map = pygame.transform.scale(sub_map, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_map, (0, 0))

    # プレイヤー描画はscaleを反映させる必要あり
    # Player.drawの中のscale_x, scale_yをズーム倍率に合わせて修正
    def draw(self, surface, cam_x, cam_y, zoom):
      scale_x = (SCREEN_WIDTH / CAMERA_WIDTH) * zoom
      scale_y = (SCREEN_HEIGHT / CAMERA_HEIGHT) * zoom
      screen_x = (self.x - cam_x) * scale_x
      screen_y = SCREEN_HEIGHT - \
          ((self.y - cam_y) * scale_y) - self.height * scale_y
      rect = pygame.Rect(screen_x, screen_y, self.width *
                         scale_x, self.height * scale_y)
      pygame.draw.rect(surface, (255, 0, 0), rect)

    # 呼び出しも変更
    player.draw(screen, camera.x, camera.y, zoom_scale)

    # --- 描画 ---
    camera_rect = pygame.Rect(int(camera.x), MAP_HEIGHT - int(camera.y) - int(CAMERA_HEIGHT),
                              int(CAMERA_WIDTH), int(CAMERA_HEIGHT))
    sub_map = map_image.subsurface(camera_rect)
    scaled_map = pygame.transform.scale(sub_map, (SCREEN_WIDTH, SCREEN_HEIGHT))
    screen.blit(scaled_map, (0, 0))

    player.draw(screen, camera.x, camera.y)

    font = pygame.font.SysFont(None, 24)
    if clicked_map_pos:
      text = font.render(
          f"Clicked Pos: ({clicked_map_pos[0]:.1f}, {clicked_map_pos[1]:.1f})", True, (255, 255, 255))
      screen.blit(text, (10, 10))

    text2 = font.render(
        f"Player Pos: ({player.x:.1f}, {player.y:.1f})", True, (255, 255, 255))
    screen.blit(text2, (SCREEN_WIDTH - 250, 10))

    # --- 全体マップ表示（画面右側） ---

    # 透明な背景サーフェス（SRCALPHA指定で透明度を扱う）
    overview_surface = pygame.Surface(
        (overview_width, overview_height), pygame.SRCALPHA)
    overview_surface.set_alpha(200)  # 透明度 40%（255 × 0.4 ≒ 102）

    # 縮小マップを貼り付け
    overview_surface.blit(map_overview, (0, 0))

    # 表示位置（右上に10px余白を持たせる）
    overview_rect = overview_surface.get_rect(topright=(SCREEN_WIDTH - 10, 10))
    screen.blit(overview_surface, overview_rect)

    # 白い枠線を描く
    pygame.draw.rect(screen, (255, 255, 255), overview_rect, 2)

    # プレイヤーの位置を赤い点で表示（縮小比を使って位置を変換）
    scale_x = overview_width / MAP_WIDTH
    scale_y = overview_height / MAP_HEIGHT

    player_dot_x = int(player.x * scale_x)
    player_dot_y = int((MAP_HEIGHT - player.y) * scale_y)  # 上が0になるよう反転

    dot_pos = (overview_rect.left + player_dot_x,
               overview_rect.top + player_dot_y)
    pygame.draw.circle(screen, (255, 0, 0), dot_pos, 4)

    pygame.display.flip()

  pygame.quit()
  sys.exit()


if __name__ == "__main__":
  main()
