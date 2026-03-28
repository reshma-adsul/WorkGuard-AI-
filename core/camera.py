"""
WorkGuard AI - Camera Surveillance Module
Detects user presence and face identity using webcam.

States:
  OWNER_PRESENT   → Original user baitha hai (light monitoring)
  NO_ONE          → Koi nahi baitha (standby)
  STRANGER        → Koi aur aa gaya (FULL ALERT mode)
"""

import cv2
import os
import json
import time
import threading
import datetime
import numpy as np
from pathlib import Path

# Try importing face_recognition (heavy library)
try:
    import face_recognition
    FACE_RECOGNITION_OK = True
except ImportError:
    FACE_RECOGNITION_OK = False

# ── States ────────────────────────────────────────────────────────────────────
STATE_NO_ONE        = "NO_ONE"
STATE_OWNER_PRESENT = "OWNER_PRESENT"
STATE_STRANGER      = "STRANGER"
STATE_UNKNOWN       = "UNKNOWN"  # Face detected but not registered yet

# ── CameraGuard Class ─────────────────────────────────────────────────────────
class CameraGuard:
    """
    Continuously monitors webcam.
    Detects presence, identifies face, triggers alerts.
    """

    OWNER_PROFILE_FILE = "owner_face_profile.npy"
    STATE_LOG_FILE     = "camera_events.jsonl"

    def __init__(self, data_dir: str = ".", alert_manager=None, on_state_change=None):
        self.data_dir        = Path(data_dir)
        self.alert_manager   = alert_manager
        self.on_state_change = on_state_change  # Callback jab state change ho

        self.current_state   = STATE_NO_ONE
        self.owner_encoding  = None   # Face encoding of original user
        self.running         = False
        self._thread         = None
        self._cap            = None
        self._last_alert_time = 0
        self.state_log       = []

        # Stats
        self.stats = {
            "frames_processed": 0,
            "owner_detections": 0,
            "stranger_detections": 0,
            "no_one_count": 0,
            "last_face_time": None,
        }

        self._load_owner_profile()

    # ── Profile management ────────────────────────────────────────────────────
    def _load_owner_profile(self):
        profile_path = self.data_dir / self.OWNER_PROFILE_FILE
        if profile_path.exists():
            self.owner_encoding = np.load(str(profile_path))
            print(f"  ✅ Owner face profile loaded")

    def has_owner_profile(self) -> bool:
        return self.owner_encoding is not None

    def register_owner(self, num_samples: int = 10) -> dict:
        """
        Capture owner's face from webcam and save encoding.
        Call this once during setup with original user.
        """
        print("\n  📸 FACE REGISTRATION")
        print("  ─────────────────────────────────────")
        print("  Tumhara face register ho raha hai...")
        print("  Camera ke saamne seedha dekho")
        print(f"  {num_samples} samples liye jaayenge\n")

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return {"success": False, "error": "Camera nahi khula"}

        encodings = []
        attempts  = 0
        max_attempts = num_samples * 5

        while len(encodings) < num_samples and attempts < max_attempts:
            ret, frame = cap.read()
            if not ret:
                attempts += 1
                continue

            # Show live feed with instructions
            display = frame.copy()
            cv2.putText(display, f"Samples: {len(encodings)}/{num_samples}",
                       (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(display, "Camera ke saamne dekho",
                       (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.imshow("WorkGuard AI - Face Registration", display)
            cv2.waitKey(1)

            if FACE_RECOGNITION_OK:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb)
                if face_locations:
                    encoding = face_recognition.face_encodings(rgb, face_locations)[0]
                    encodings.append(encoding)
                    print(f"  ✓ Sample {len(encodings)}/{num_samples} captured")
                    time.sleep(0.3)
            else:
                # Fallback: OpenCV haar cascade
                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self._haar_detect(gray)
                if len(faces) > 0:
                    encodings.append(np.array([1.0]))  # Dummy encoding
                    print(f"  ✓ Sample {len(encodings)}/{num_samples} captured")
                    time.sleep(0.3)

            attempts += 1

        cap.release()
        cv2.destroyAllWindows()

        if len(encodings) < 3:
            return {"success": False, "error": "Enough face samples nahi mile. Lighting check karo."}

        # Average encoding save karo
        if FACE_RECOGNITION_OK:
            mean_encoding = np.mean(encodings, axis=0)
        else:
            mean_encoding = np.array([1.0])

        self.data_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(self.data_dir / self.OWNER_PROFILE_FILE), mean_encoding)
        self.owner_encoding = mean_encoding

        print(f"\n  ✅ Face profile saved! ({len(encodings)} samples)")
        return {"success": True, "samples": len(encodings)}

    # ── Haar Cascade fallback ─────────────────────────────────────────────────
    _haar_cascade = None

    def _haar_detect(self, gray_frame):
        """OpenCV built-in face detection (no extra library needed)"""
        if self._haar_cascade is None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar_cascade = cv2.CascadeClassifier(cascade_path)
        return self._haar_cascade.detectMultiScale(
            gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
        )

    # ── Core detection logic ─────────────────────────────────────────────────
    def _analyze_frame(self, frame) -> str:
        """
        Analyze one frame and return detected state.
        Returns: STATE_NO_ONE, STATE_OWNER_PRESENT, STATE_STRANGER, STATE_UNKNOWN
        """
        if FACE_RECOGNITION_OK and self.owner_encoding is not None:
            return self._face_recognition_detect(frame)
        else:
            return self._haar_presence_detect(frame)

    def _face_recognition_detect(self, frame) -> str:
        """Full face recognition — identifies WHO is present"""
        rgb            = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Resize for speed (process at 1/4 size)
        small          = cv2.resize(rgb, (0, 0), fx=0.25, fy=0.25)
        face_locations = face_recognition.face_locations(small)

        if not face_locations:
            return STATE_NO_ONE

        # Scale back up
        face_locations_full = [(t*4, r*4, b*4, l*4) for (t, r, b, l) in face_locations]
        encodings = face_recognition.face_encodings(rgb, face_locations_full)

        if not encodings:
            return STATE_NO_ONE

        # Compare with owner
        matches   = face_recognition.compare_faces(
            [self.owner_encoding], encodings[0], tolerance=0.55
        )
        distances = face_recognition.face_distance([self.owner_encoding], encodings[0])

        if matches[0]:
            return STATE_OWNER_PRESENT
        else:
            return STATE_STRANGER

    def _haar_presence_detect(self, frame) -> str:
        """Fallback — only detects presence, not identity"""
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._haar_detect(gray)

        if len(faces) == 0:
            return STATE_NO_ONE
        elif self.owner_encoding is not None:
            # Owner registered hai but face_recognition nahi — assume stranger
            return STATE_UNKNOWN
        else:
            # No profile — just detect presence
            return STATE_OWNER_PRESENT

    # ── State machine ─────────────────────────────────────────────────────────
    def _update_state(self, new_state: str):
        """Handle state transitions and fire alerts"""
        if new_state == self.current_state:
            return

        old_state = self.current_state
        self.current_state = new_state

        # Log event
        event = {
            "time": datetime.datetime.now().isoformat(),
            "from": old_state,
            "to":   new_state,
        }
        self.state_log.append(event)

        log_file = self.data_dir / self.STATE_LOG_FILE
        with open(log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

        print(f"\n  🎥 Camera State: {old_state} → {new_state}")

        # Callback — recorder ko batao recording mode change karo
        if self.on_state_change:
            self.on_state_change(new_state)

        # Alert fire karo
        now = time.time()
        if new_state == STATE_STRANGER:
            # Spam prevent karo — har 30 sec mein ek alert
            if now - self._last_alert_time > 30:
                self._last_alert_time = now
                print("  🔴 ALERT: STRANGER DETECTED!")
                if self.alert_manager:
                    self.alert_manager.fire_anomaly_alert(
                        anomaly_type="UNAUTHORIZED_PERSON_DETECTED",
                        score=0.95,
                        details={"window": "Camera Feed", "process": "camera_guard"}
                    )

        elif new_state == STATE_NO_ONE:
            print("  💤 No one at desk — Standby mode")

        elif new_state == STATE_OWNER_PRESENT:
            print("  ✅ Owner detected — Normal mode")

    # ── Main loop ─────────────────────────────────────────────────────────────
    def _camera_loop(self):
        """Main camera monitoring loop — runs in background thread"""
        self._cap = cv2.VideoCapture(0)

        if not self._cap.isOpened():
            print("  ❌ Camera nahi khula! Webcam check karo.")
            return

        print("  📷 Camera monitoring started")

        # State smoothing — 3 consecutive same readings ke baad hi change karo
        state_buffer   = []
        SMOOTH_WINDOW  = 3
        frame_interval = 2.0  # Har 2 sec mein ek frame analyze karo

        last_frame_time = 0

        while self.running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            now = time.time()
            if now - last_frame_time < frame_interval:
                time.sleep(0.1)
                continue

            last_frame_time = now
            self.stats["frames_processed"] += 1

            # Analyze frame
            detected_state = self._analyze_frame(frame)

            # Smoothing
            state_buffer.append(detected_state)
            if len(state_buffer) > SMOOTH_WINDOW:
                state_buffer.pop(0)

            # Majority vote
            if len(state_buffer) == SMOOTH_WINDOW:
                majority = max(set(state_buffer), key=state_buffer.count)
                if state_buffer.count(majority) >= 2:
                    self._update_state(majority)

            # Update stats
            if detected_state == STATE_OWNER_PRESENT:
                self.stats["owner_detections"] += 1
                self.stats["last_face_time"] = datetime.datetime.now().isoformat()
            elif detected_state == STATE_STRANGER:
                self.stats["stranger_detections"] += 1
                self.stats["last_face_time"] = datetime.datetime.now().isoformat()
            elif detected_state == STATE_NO_ONE:
                self.stats["no_one_count"] += 1

        self._cap.release()
        print("  📷 Camera monitoring stopped")

    # ── Public API ────────────────────────────────────────────────────────────
    def start(self):
        """Start camera monitoring in background thread"""
        self.running = True
        self._thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop camera monitoring"""
        self.running = False
        if self._cap:
            self._cap.release()

    def get_status(self) -> dict:
        return {
            "state":          self.current_state,
            "has_profile":    self.has_owner_profile(),
            "stats":          self.stats,
            "state_log":      self.state_log[-20:],
            "face_recognition_available": FACE_RECOGNITION_OK,
        }

    def capture_intruder_photo(self, save_dir: str) -> str:
        """Take a photo of the intruder and save it"""
        if not self._cap or not self._cap.isOpened():
            cap = cv2.VideoCapture(0)
        else:
            cap = self._cap

        ret, frame = cap.read()
        if ret:
            fname = f"intruder_{datetime.datetime.now().strftime('%H%M%S')}.jpg"
            fpath = Path(save_dir) / fname
            cv2.imwrite(str(fpath), frame)
            return fname
        return None
