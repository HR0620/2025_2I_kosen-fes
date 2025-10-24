import os
import pygame
import sys
import math
import time

pygame.init()
pygame.mixer.init()

# --- Constants ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = SCREEN_WIDTH * 10 // 16  # 16:10 Aspect Ratio
FPS = 60
CAMERA_WIDTH_2P = 375  # Camera width for 2P (split screen)
CAMERA_HEIGHT = 400    # Camera height (base)
# Camera width for 1P (fullscreen, matching screen aspect ratio)
CAMERA_WIDTH_1P = int(CAMERA_HEIGHT * (SCREEN_WIDTH / SCREEN_HEIGHT))

TIME_LIMIT = 300  # Time limit (seconds)
GOAL_Y = 30000.0  # Goal Y coordinate
ZOOM_OUT_SCALE = 0.5
ZOOM_SMOOTHING = 0.1

IMAGE_PATH = "./hisayoshi/image"
SOUND_PATH = "./hisayoshi/sound"
BGM_PATH = f"{SOUND_PATH}/bgm"
EFFECT_PATH = f"{SOUND_PATH}/effect"
VOICE_PATH = f"{SOUND_PATH}/voice"

def load_voice_files():
  """hisayoshi/sound/voice フォルダ内の全てのmp3をロードして辞書で返す"""
  voices = {}
  if not os.path.exists(VOICE_PATH):
    print(f"[WARNING] VOICE_PATH not found: {VOICE_PATH}")
    return voices

  for file in os.listdir(VOICE_PATH):
    if file.lower().endswith(".mp3"):
      name = os.path.splitext(file)[0]  # 例: 'areyouready'
      full_path = os.path.join(VOICE_PATH, file)
      try:
        voices[name] = pygame.mixer.Sound(full_path)
      except pygame.error as e:
        print(f"[ERROR] Failed to load {file}: {e}")
  print(f"[INFO] Loaded {len(voices)} voice files.")
  return voices

voice_dict = load_voice_files()

# --- Game Screen Initialization ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("OnlyUp-style Game (1P/2P)")
clock = pygame.time.Clock()

# --- Load Map Image ---
try:
  map_image = pygame.image.load(f"{IMAGE_PATH}/map_highres.png").convert_alpha()
except pygame.error as e:
  print(f"Error loading map_highres.png: {e}. Please ensure the file exists.")
  pygame.quit()
  sys.exit()

MAP_WIDTH, MAP_HEIGHT = map_image.get_size()

# --- Sound Settings and Channels ---
try:
  jump_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/キックの素振り3.mp3")
  blue_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/ボヨン.mp3")
  green_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/爆発1.mp3")
  fall_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/ジャンプの着地.mp3")
  wind_sound = pygame.mixer.Sound(f"{EFFECT_PATH}/Wind-Synthetic_Ambi01-1.mp3")
except pygame.error as e:
  print(
      f"Error loading sound files. Check file paths and formats: {e}. Some sounds may not play."
  )
  # Assign None to sounds that failed to load, to avoid crashes later
  jump_sound = blue_sound = green_sound = fall_sound = wind_sound = None

# Channel allocation (SFX and Wind)
CHANNEL_P1_SFX = pygame.mixer.Channel(0)
CHANNEL_P2_SFX = pygame.mixer.Channel(1)
CHANNEL_P1_WIND = pygame.mixer.Channel(2)
CHANNEL_P2_WIND = pygame.mixer.Channel(3)

# Start wind sound loop (initial volume 0.0)
if wind_sound:
  CHANNEL_P1_WIND.play(wind_sound, loops=-1)
  CHANNEL_P2_WIND.play(wind_sound, loops=-1)
  CHANNEL_P1_WIND.set_volume(0.0)
  CHANNEL_P2_WIND.set_volume(0.0)

# --- Load Player Image & Scale ---
try:
  original_image = pygame.image.load(f"{IMAGE_PATH}/muroya.png").convert_alpha()
except pygame.error as e:
  print(f"Error loading muroya.png: {e}. Please ensure the file exists.")
  pygame.quit()
  sys.exit()

scaled_image = pygame.transform.scale(original_image, (100, 150))
image_right = scaled_image
image_left = pygame.transform.flip(scaled_image, True, False)

# 1/20 scaled overview map
overview_width = 120
overview_height = int(MAP_HEIGHT * (overview_width / MAP_WIDTH))
map_overview = pygame.transform.scale(
    map_image, (overview_width, overview_height))

# --- Player Class ---
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
    # Play sound only if it was loaded successfully
    if sound and self.sfx_channel:
      self.sfx_channel.play(sound)

  def update(self, keys, control_map):
    if self.is_goal:
      return

    self.is_zooming_out = keys[control_map['zoom_out']]

    accel = 0.375 if self.on_ground else 0.025
    max_speed = self.speed

    if self.vy < -1.0:
      speed_factor = min(abs(self.vy) / 10, 1.0)
      self.wind_channel.set_volume(speed_factor * 0.8)
    else:
      self.wind_channel.set_volume(0.0)

    if keys[control_map['left']]:
      self.vx -= accel
      self.facing_right = True  # Left movement -> facing right
    elif keys[control_map['right']]:
      self.vx += accel
      self.facing_right = False  # Right movement -> facing left
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
        if "yoisho" in voice_dict:
          voice_dict["yoisho"].play()

      elif self.wall_jump_cooldown == 0:
        if self.check_collision(self.x - 0.2, self.y) or self.check_collision(self.x + 0.2, self.y):
          self.vy = self.jump_speed * 0.8
          if self.check_collision(self.x - 0.2, self.y):
            self.vx = self.speed * 0.7
          else:
            self.vx = -self.speed * 0.7
          self.wall_jump_cooldown = 10
          self.play_sound(jump_sound)
          if "yoisho" in voice_dict:
            voice_dict["yoisho"].play()

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
          try:
            r, g, b, a = map_image.get_at((px, img_y))
            if r < 10 and g < 10 and b < 10 and a > 0:
              return True
          except IndexError:
            # This can happen if coordinates are slightly out of bounds
            # during calculation, treat as no collision.
            pass
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
          try:
            r, g, b, a = map_image.get_at((px, img_y))
            if r == 0 and g == 0 and b == 255:
              return 'blue'
            elif r == 0 and g == 255 and b == 0:
              return 'green'
          except IndexError:
            pass
    return None

# --- Camera Class ---
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


# --- Helper Functions ---

def draw_text_border(surface, text, font, color, border_color, x, y, border_size=1):
  """Helper function to draw text with an outline."""

  # Draw border (outside)
  for dx in range(-border_size, border_size + 1):
    for dy in range(-border_size, border_size + 1):
      if dx != 0 or dy != 0:
        border_surface = font.render(text, True, border_color)
        surface.blit(border_surface, (x + dx, y + dy))

  # Draw text (inside)
  text_surface = font.render(text, True, color)
  surface.blit(text_surface, (x, y))


def switch_bgm(target, current_bgm):
  """Common BGM switcher (uses pygame.mixer.music)."""
  if target != current_bgm:
    print(f"[BGM] Switching to: {target}")
    try:
      if pygame.mixer.music.get_busy():
        pygame.mixer.music.stop()

      if target == "original":
        pygame.mixer.music.load(f"{BGM_PATH}/The Dark Eternal Night.mp3")
      elif target == "mid":
        pygame.mixer.music.load(f"{BGM_PATH}/zanzou no hiyu.mp3")
      elif target == "high":
        pygame.mixer.music.load(f"{BGM_PATH}/Outer Space.mp3")

      pygame.mixer.music.play(-1, fade_ms=2000)
      return target
    except Exception as e:
      print(f"[ERROR] Failed to load/play BGM: {e}")
      return current_bgm
  return current_bgm


def draw_overview_map(main_surface, player1, player2, ow_width, ow_height, map_w, map_h, font, overview_rect):
  """
  Helper function to draw the overview map.
  player2 can be None for 1P mode.
  """

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
  BORDER_COLOR = (255, 215, 0)  # Gold

  # --- P1 Position (Red) ---
  player1_dot_x = int(player1.x * scale_x)
  player1_dot_y = int((map_h - player1.y) * scale_y)
  dot_pos1 = (overview_rect.left + player1_dot_x,
              overview_rect.top + player1_dot_y)

  pygame.draw.circle(main_surface, BORDER_COLOR,
                     dot_pos1, PLAYER_BORDER_RADIUS)
  pygame.draw.circle(main_surface, (255, 0, 0), dot_pos1,
                     PLAYER_DOT_RADIUS)  # Red (1P)

  # --- P2 Position (Blue) - Only if player2 exists ---
  if player2:
    player2_dot_x = int(player2.x * scale_x)
    player2_dot_y = int((map_h - player2.y) * scale_y)
    dot_pos2 = (overview_rect.left + player2_dot_x,
                overview_rect.top + player2_dot_y)
    pygame.draw.circle(main_surface, BORDER_COLOR,
                       dot_pos2, PLAYER_BORDER_RADIUS)
    pygame.draw.circle(main_surface, (0, 0, 255), dot_pos2,
                       PLAYER_DOT_RADIUS)  # Blue (2P)

  # Draw Goal Line
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


def draw_game_view(surface, player, camera, cam_width, cam_height, zoom_scale, player_label, font):
  """
  Helper function to draw an individual game screen.
  If player_label is None, the label is not drawn (for 1P mode).
  """

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

  # Draw player label (1P or 2P) if provided
  if player_label:
    player_id_color = (255, 0, 0) if player.player_id == 1 else (0, 0, 255)
    draw_text_border(surface, player_label, font, player_id_color,
                     (255, 255, 255), 10, 10, border_size=2)

  # Show coordinates (using integers)
  text_pos = font.render(
      f"Pos: ({int(player.x)}, {int(player.y)})", True, (255, 255, 255))
  surface.blit(text_pos, (surface.get_width() -
                          text_pos.get_width() - 10, 10))

  # Timer drawing logic has been moved to the main loop


def draw_end_screen(surface, message, font):
  """Draws the game over screen."""
  surface.fill((0, 0, 0))
  text_render = font.render(message, True, (255, 255, 255))
  rect = text_render.get_rect(
      center=(surface.get_width() // 2, surface.get_height() // 2))
  surface.blit(text_render, rect)
  pygame.display.flip()
  time.sleep(3)


def draw_select_mode_screen(surface, title_font, button_font, btn_1p_rect, btn_2p_rect):
  """Draws the mode selection screen."""
  surface.fill((30, 30, 50))  # Dark blue background

  # Title
  title_text = "OnlyUp-style Game"
  title_width = title_font.size(title_text)[0]
  draw_text_border(surface, title_text, title_font, (255, 255, 255), (0, 0, 0),
                   surface.get_width() // 2 - title_width // 2,
                   surface.get_height() // 4, 2)

  # 1P Button
  pygame.draw.rect(surface, (0, 100, 200), btn_1p_rect, border_radius=10)
  pygame.draw.rect(surface, (255, 255, 255), btn_1p_rect, 3, border_radius=10)
  btn_1p_text = button_font.render("1P Play", True, (255, 255, 255))
  surface.blit(btn_1p_text, btn_1p_text.get_rect(center=btn_1p_rect.center))

  # 2P Button
  pygame.draw.rect(surface, (200, 0, 100), btn_2p_rect, border_radius=10)
  pygame.draw.rect(surface, (255, 255, 255), btn_2p_rect, 3, border_radius=10)
  btn_2p_text = button_font.render("2P Versus", True, (255, 255, 255))
  surface.blit(btn_2p_text, btn_2p_text.get_rect(center=btn_2p_rect.center))


# --- Main Game ---
def main():
  # Game States
  STATE_SELECT_MODE = 0
  STATE_PLAYING = 1
  STATE_GAME_OVER = 2

  game_state = STATE_SELECT_MODE
  play_mode = 0  # 1 for 1P, 2 for 2P

  player1 = None
  player2 = None
  camera1 = None
  camera2 = None

  current_zoom_p1 = 1.0
  current_zoom_p2 = 1.0

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
  game_start_time = 0
  camera_smoothing = 0.15
  game_end_message = ""

  # Fonts
  font = pygame.font.SysFont(None, 36)
  title_font = pygame.font.SysFont(None, 72)
  button_font = pygame.font.SysFont(None, 48)

  # Overview map position (Top Right)
  overview_rect = pygame.Rect(0, 0, overview_width, overview_height)
  overview_rect.topright = (SCREEN_WIDTH - 10, 10)

  # Mode Select Button Rects
  BTN_WIDTH = 250
  BTN_HEIGHT = 80
  center_x = SCREEN_WIDTH // 2
  center_y = SCREEN_HEIGHT // 2

  btn_1p_rect = pygame.Rect(center_x - BTN_WIDTH // 2,
                            center_y - BTN_HEIGHT, BTN_WIDTH, BTN_HEIGHT)
  btn_2p_rect = pygame.Rect(center_x - BTN_WIDTH // 2,
                            center_y + BTN_HEIGHT // 2, BTN_WIDTH, BTN_HEIGHT)

  running = True
  while running:
    clock.tick(FPS)
    keys = pygame.key.get_pressed()

    # --- Event Handling ---
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False

      if game_state == STATE_SELECT_MODE:
        if event.type == pygame.MOUSEBUTTONDOWN:
          if event.button == 1:  # Left click
            if btn_1p_rect.collidepoint(event.pos):
              play_mode = 1
              game_state = STATE_PLAYING
              game_start_time = time.time()
              # 1P Initialization
              player1 = Player(1, image_right, image_left, 2800.0,
                               CHANNEL_P1_SFX, CHANNEL_P1_WIND)
              camera1 = Camera(CAMERA_WIDTH_1P, CAMERA_HEIGHT)
              current_bgm = switch_bgm("original", "")

            elif btn_2p_rect.collidepoint(event.pos):
              play_mode = 2
              game_state = STATE_PLAYING
              game_start_time = time.time()
              # 2P Initialization
              player1 = Player(1, image_right, image_left, 2800.0,
                               CHANNEL_P1_SFX, CHANNEL_P1_WIND)
              player2 = Player(2, image_right, image_left, 3200.0,
                               CHANNEL_P2_SFX, CHANNEL_P2_WIND)
              camera1 = Camera(CAMERA_WIDTH_2P, CAMERA_HEIGHT)
              camera2 = Camera(CAMERA_WIDTH_2P, CAMERA_HEIGHT)
              current_bgm = switch_bgm("original", "")

      elif game_state == STATE_PLAYING:
        # Toggle overview map
        if event.type == pygame.KEYDOWN:
          if event.key == pygame.K_m:
            show_overview_map = not show_overview_map

    # --- Game Logic ---
    if game_state == STATE_PLAYING:

      # --- Time Calculation ---
      current_time = time.time()
      elapsed_time = current_time - game_start_time
      remaining_time = max(0, TIME_LIMIT - elapsed_time)
      timer_text = f"TIME: {int(remaining_time):03d}s"

      # --- Updates (based on mode) ---
      if play_mode == 1:
        player1.update(keys, control_map_p1)

        # BGM switch (1P)
        if player1.y < 9500:
          current_bgm = switch_bgm("original", current_bgm)
        elif player1.y < 25000:
          current_bgm = switch_bgm("mid", current_bgm)
        else:
          current_bgm = switch_bgm("high", current_bgm)

        # Zoom (1P)
        target_zoom_p1 = ZOOM_OUT_SCALE if player1.is_zooming_out else 1.0
        current_zoom_p1 += (target_zoom_p1 - current_zoom_p1) * ZOOM_SMOOTHING

        # Camera (1P)
        camera1.update(player1, camera_smoothing, current_zoom_p1)

      elif play_mode == 2:
        player1.update(keys, control_map_p1)
        player2.update(keys, control_map_p2)

        # BGM switch (2P)
        highest_y = max(player1.y, player2.y)
        if highest_y < 9500:
          current_bgm = switch_bgm("original", current_bgm)
        elif highest_y < 25000:
          current_bgm = switch_bgm("mid", current_bgm)
        else:
          current_bgm = switch_bgm("high", current_bgm)

        # Zoom (2P)
        target_zoom_p1 = ZOOM_OUT_SCALE if player1.is_zooming_out else 1.0
        current_zoom_p1 += (target_zoom_p1 - current_zoom_p1) * ZOOM_SMOOTHING
        target_zoom_p2 = ZOOM_OUT_SCALE if player2.is_zooming_out else 1.0
        current_zoom_p2 += (target_zoom_p2 - current_zoom_p2) * ZOOM_SMOOTHING

        # Camera (2P)
        camera1.update(player1, camera_smoothing, current_zoom_p1)
        camera2.update(player2, camera_smoothing, current_zoom_p2)

      # --- Game Over Check ---
      game_over = False
      if remaining_time <= 0:
        game_over = True
        game_end_message = "TIME OVER!"

      elif play_mode == 1 and player1.is_goal:
        game_over = True
        game_end_message = "GOAL! YOU MADE IT!"

      elif play_mode == 2 and player2:  # Check if player2 exists
        if player1.is_goal or (player2 and player2.is_goal):
          game_over = True
          if player1.is_goal and player2 and player2.is_goal:
            game_end_message = "DRAW! Both players reached the goal!"
          elif player1.is_goal:
            game_end_message = "1P WINS! (Goal Reached)"
          else:
            game_end_message = "2P WINS! (Goal Reached)"

      if game_over:
        game_state = STATE_GAME_OVER
        pygame.mixer.music.stop()

      # --- Drawing ---
      screen.fill((0, 0, 0))

      # Prepare Timer Render
      timer_text_render = font.render(timer_text, True, (255, 0, 0))
      timer_rect = timer_text_render.get_rect()

      if play_mode == 1:
        # Draw 1P Game View (Fullscreen)
        draw_game_view(screen, player1, camera1, CAMERA_WIDTH_1P,
                       CAMERA_HEIGHT, current_zoom_p1, None, font)

        # Draw Timer (Top right of fullscreen)
        timer_rect.topright = (SCREEN_WIDTH - 10, 50)
        screen.blit(timer_text_render, timer_rect)

        # Draw Overview Map
        if show_overview_map:
          draw_overview_map(screen, player1, None,
                            overview_width, overview_height, MAP_WIDTH, MAP_HEIGHT, font, overview_rect)

      elif play_mode == 2:
        # Draw 1P Game View (Left)
        draw_game_view(SCREEN_SURFACE_P1, player1, camera1, CAMERA_WIDTH_2P,
                       CAMERA_HEIGHT, current_zoom_p1, "1P", font)

        # Draw 2P Game View (Right)
        draw_game_view(SCREEN_SURFACE_P2, player2, camera2,
                       CAMERA_WIDTH_2P, CAMERA_HEIGHT, current_zoom_p2, "2P", font)

        # Draw Timer (Top right of 1P screen)
        timer_rect.topright = (HALF_SCREEN_WIDTH - 10, 50)
        screen.blit(timer_text_render, timer_rect)

        # Draw Divider Line
        pygame.draw.line(screen, (0, 0, 0), (HALF_SCREEN_WIDTH, 0),
                         (HALF_SCREEN_WIDTH, SCREEN_HEIGHT), 3)

        # Draw Overview Map
        if show_overview_map:
          draw_overview_map(screen, player1, player2,
                            overview_width, overview_height, MAP_WIDTH, MAP_HEIGHT, font, overview_rect)

    # --- Other States ---
    elif game_state == STATE_SELECT_MODE:
      draw_select_mode_screen(
          screen, title_font, button_font, btn_1p_rect, btn_2p_rect)

    elif game_state == STATE_GAME_OVER:
      draw_end_screen(screen, game_end_message, font)
      running = False  # End game after showing message

    pygame.display.flip()

  pygame.quit()
  sys.exit()


if __name__ == "__main__":
  main()
