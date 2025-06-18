import os
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import QUrl, pyqtSignal, QObject

class SoundManagerQt(QObject):
    """
    Manages sound effects for the application using PyQt5's QSoundEffect.
    Plays alert sounds and sounds for value changes (up/down).
    Communicates status messages back to the GUI via a signal.
    """
    status_message_signal = pyqtSignal(str, str) # message, color ('info', 'warning', 'danger')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sound_system_available = False
        self.alert_sound_effect = None
        self.up_sound_effect = None
        self.down_sound_effect = None

        self._initialize_sound_system()

    def _initialize_sound_system(self):
        """Initializes QSoundEffect instances and loads sound files."""
        # Check if QSoundEffect can be instantiated, indicating multimedia support
        try:
            temp_effect = QSoundEffect()
            self.sound_system_available = temp_effect.isSupported()
            del temp_effect # Clean up temp object
        except Exception as e:
            self.status_message_signal.emit(f"QSoundEffect initialization failed: {e}. Sound disabled.", 'danger')
            self.sound_system_available = False
            return

        if not self.sound_system_available:
            self.status_message_signal.emit("Sound system not fully available or supported. Sound effects disabled.", 'warning')
            return

        self._load_sounds()

        if not (self.alert_sound_effect and self.up_sound_effect and self.down_sound_effect):
            self.sound_system_available = False
            self.status_message_signal.emit("One or more sound files failed to load. Sound effects disabled.", 'warning')

    def _load_sounds(self):
        """Loads sound files for alerts and value changes."""
        script_dir = os.path.dirname(__file__)
        
        # Define sound file paths relative to the script
        # Users should place alert.wav, up.wav, down.wav in the same directory
        alert_sound_file_path = os.path.join(script_dir, "alert.wav")
        up_sound_file_path = os.path.join(script_dir, "up.wav")
        down_sound_file_path = os.path.join(script_dir, "down.wav")

        try:
            # Alert sound
            self.alert_sound_effect = QSoundEffect()
            if os.path.exists(alert_sound_file_path):
                self.alert_sound_effect.setSource(QUrl.fromLocalFile(alert_sound_file_path))
                if not self.alert_sound_effect.isLoaded():
                    self.status_message_signal.emit(f"Failed to load alert sound: {alert_sound_file_path}", 'warning')
                    self.alert_sound_effect = None
            else:
                self.status_message_signal.emit(f"Alert sound file not found: {alert_sound_file_path}", 'warning')
                self.alert_sound_effect = None

            # Up sound
            self.up_sound_effect = QSoundEffect()
            if os.path.exists(up_sound_file_path):
                self.up_sound_effect.setSource(QUrl.fromLocalFile(up_sound_file_path))
                if not self.up_sound_effect.isLoaded():
                    self.status_message_signal.emit(f"Failed to load up sound: {up_sound_file_path}", 'warning')
                    self.up_sound_effect = None
            else:
                self.status_message_signal.emit(f"Up sound file not found: {up_sound_file_path}", 'warning')
                self.up_sound_effect = None

            # Down sound
            self.down_sound_effect = QSoundEffect()
            if os.path.exists(down_sound_file_path):
                self.down_sound_effect.setSource(QUrl.fromLocalFile(down_sound_file_path))
                if not self.down_sound_effect.isLoaded():
                    self.status_message_signal.emit(f"Failed to load down sound: {down_sound_file_path}", 'warning')
                    self.down_sound_effect = None
            else:
                self.status_message_signal.emit(f"Down sound file not found: {down_sound_file_path}", 'warning')
                self.down_sound_effect = None

        except Exception as e:
            self.status_message_signal.emit(f"Error loading sound files: {e}. Sound effects disabled.", 'danger')
            self.sound_system_available = False

    def play_alert_sound(self, play_enabled):
        """Plays a short alert sound effect if enabled and available."""
        if self.sound_system_available and self.alert_sound_effect and play_enabled:
            # Check if sound is currently playing to prevent overlap, QSoundEffect usually handles this
            if not self.alert_sound_effect.isPlaying():
                try:
                    self.alert_sound_effect.play()
                except Exception as e:
                    self.status_message_signal.emit(f"Error playing alert sound: {e}. Sound disabled.", 'danger')
                    self.sound_system_available = False

    def play_change_sound(self, direction, play_enabled):
        """Plays 'up' or 'down' sound based on value change if enabled and available."""
        if self.sound_system_available and play_enabled:
            # Prevent overlap
            if not (self.up_sound_effect and self.up_sound_effect.isPlaying()) and \
               not (self.down_sound_effect and self.down_sound_effect.isPlaying()):
                try:
                    if direction == 'up' and self.up_sound_effect:
                        self.up_sound_effect.play()
                    elif direction == 'down' and self.down_sound_effect:
                        self.down_sound_effect.play()
                except Exception as e:
                    self.status_message_signal.emit(f"Error playing change sound ({direction}): {e}. Sound disabled.", 'danger')
                    self.sound_system_available = False

    # QSoundEffect objects are automatically managed by Qt's event loop.
    # There's no explicit `quit_mixer` equivalent needed like in Pygame.
    # When the application exits, these resources are automatically released.

