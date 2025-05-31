import os
import queue # For sending status messages back to the GUI

# Try importing pygame for audio feedback
try:
    import pygame
    pygame.mixer.init()
    CAN_PLAY_SOUND = True
except ImportError:
    print("Pygame library not found. Sound effects will be disabled.")
    CAN_PLAY_SOUND = False
except Exception as e:
    print(f"Error initializing Pygame mixer: {e}. Sound effects will be disabled.")
    CAN_PLAY_SOUND = False

class SoundManager:
    def __init__(self, status_queue):
        self.status_queue = status_queue
        self.sound_system_available = CAN_PLAY_SOUND
        self.alert_sound = None
        self.up_sound = None
        self.down_sound = None

        if self.sound_system_available:
            self._load_sounds()
            if not (self.alert_sound or self.up_sound or self.down_sound):
                self.sound_system_available = False
                self.status_queue.put({'type': 'status_message', 'message': "No sound files loaded. Sound effects disabled.", 'color': 'orange'})

    def _load_sounds(self):
        """Loads sound files for alerts and value changes."""
        # Assuming sound files are in the same directory as the script or a known 'sounds' subfolder
        script_dir = os.path.dirname(__file__)
        alert_sound_file_path = os.path.join(script_dir, "alert.wav")
        up_sound_file_path = os.path.join(script_dir, "up.wav")
        down_sound_file_path = os.path.join(script_dir, "down.wav")

        try:
            if os.path.exists(alert_sound_file_path):
                self.alert_sound = pygame.mixer.Sound(alert_sound_file_path)
            else:
                print(f"Warning: Alert sound file not found at {alert_sound_file_path}")
            if os.path.exists(up_sound_file_path):
                self.up_sound = pygame.mixer.Sound(up_sound_file_path)
            else:
                print(f"Warning: Up sound file not found at {up_sound_file_path}")
            if os.path.exists(down_sound_file_path):
                self.down_sound = pygame.mixer.Sound(down_sound_file_path)
            else:
                print(f"Warning: Down sound file not found at {down_sound_file_path}")

        except pygame.error as e:
            self.status_queue.put({'type': 'status_message', 'message': f"Could not load sound file: {e}. Sound effects disabled.", 'color': 'red'})
            self.sound_system_available = False
        except Exception as e:
            self.status_queue.put({'type': 'status_message', 'message': f"Error loading sounds: {e}. Sound effects disabled.", 'color': 'red'})
            self.sound_system_available = False

    def play_alert_sound(self, play_enabled):
        """Plays a short alert sound effect if enabled and available."""
        if self.sound_system_available and self.alert_sound and play_enabled:
            try:
                if not pygame.mixer.get_busy():
                    self.alert_sound.play()
            except pygame.error as e:
                self.status_queue.put({'type': 'status_message', 'message': f"Error playing alert sound: {e}. Sound disabled.", 'color': 'red'})
                self.sound_system_available = False
            except Exception as e:
                self.status_queue.put({'type': 'status_message', 'message': f"Unexpected error playing alert sound: {e}. Sound disabled.", 'color': 'red'})
                self.sound_system_available = False

    def play_change_sound(self, direction, play_enabled):
        """Plays 'up' or 'down' sound based on value change if enabled and available."""
        if self.sound_system_available and play_enabled:
            if not pygame.mixer.get_busy():
                try:
                    if direction == 'up' and self.up_sound:
                        self.up_sound.play()
                    elif direction == 'down' and self.down_sound:
                        self.down_sound.play()
                except pygame.error as e:
                    self.status_queue.put({'type': 'status_message', 'message': f"Error playing change sound ({direction}): {e}. Sound disabled.", 'color': 'red'})
                    self.sound_system_available = False
                except Exception as e:
                    self.status_queue.put({'type': 'status_message', 'message': f"Unexpected error playing change sound ({direction}): {e}. Sound disabled.", 'color': 'red'})
                    self.sound_system_available = False

    def quit_mixer(self):
        """Quits the pygame mixer."""
        if self.sound_system_available and pygame.mixer.get_init():
            pygame.mixer.quit()
            print("SoundManager: Pygame mixer quit.")
