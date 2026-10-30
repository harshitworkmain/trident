#include "sos.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "buzzer.h"
#include "config.h"
#include "settings.h"

static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static SosStatus s_sos;               // guarded by s_mux
static bool s_frameReq = false;       // guarded by s_mux
static TaskHandle_t s_netTask = nullptr;

SosStatus sos_status() {
  portENTER_CRITICAL(&s_mux);
  SosStatus s = s_sos;
  portEXIT_CRITICAL(&s_mux);
  return s;
}

bool sos_pending() {
  portENTER_CRITICAL(&s_mux);
  bool p = s_sos.phase == SOS_ACTIVE && !s_sos.received;
  portEXIT_CRITICAL(&s_mux);
  return p;
}

bool sos_take_frame_request() {
  portENTER_CRITICAL(&s_mux);
  bool r = s_frameReq;
  s_frameReq = false;
  portEXIT_CRITICAL(&s_mux);
  return r;
}

void sos_close(FrameData &f) {
  portENTER_CRITICAL(&s_mux);
  if (s_sos.phase == SOS_ACTIVE) {
    f.sos_phase = SOS_ACTIVE;
  } else if (s_sos.phase == SOS_CANCELLED && s_sos.cancel_frames_left > 0) {
    f.sos_phase = SOS_CANCELLED;
    s_sos.cancel_frames_left--;
  }
  if (f.sos_phase != SOS_NONE) {
    f.sos_press_id = s_sos.press_id;
    f.sos_pressed_ms = s_sos.pressed_uptime_ms;
  }
  portEXIT_CRITICAL(&s_mux);
}

void sos_handle_response(JsonObjectConst s) {
  uint32_t id = s["press_id"] | 0u;
  bool ackNow = false, cancelAck = false;
  portENTER_CRITICAL(&s_mux);
  if (id != 0 && id == s_sos.press_id) {
    if (s_sos.phase == SOS_ACTIVE && (s["received"] | false) && !s_sos.received) {
      s_sos.received = true;
      strlcpy(s_sos.reference_id, s["reference_id"] | "", sizeof(s_sos.reference_id));
      ackNow = true;
    } else if (s_sos.phase == SOS_CANCELLED && (s["cancelled"] | false) && !s_sos.cancel_acked) {
      s_sos.cancel_acked = true;
      s_sos.cancel_frames_left = 0;
      cancelAck = true;
    }
  }
  portEXIT_CRITICAL(&s_mux);
  if (ackNow) {
    buzzer_cue(CUE_SOS_RECEIVED);
    Serial.printf("[sos] #%u received by the control room (%s)\n", (unsigned)id,
                  s["reference_id"] | "no reference");
  }
  if (cancelAck) Serial.printf("[sos] cancel of #%u acknowledged\n", (unsigned)id);
}

// ---------------- Button task ----------------

static void wake_network() {
  if (s_netTask) xTaskNotifyGive(s_netTask);
}

static void raise_sos(uint32_t now, const char *how) {
  uint32_t id = settings_sos_next_press_id();
  portENTER_CRITICAL(&s_mux);
  s_sos.phase = SOS_ACTIVE;
  s_sos.press_id = id;
  s_sos.pressed_uptime_ms = now;
  s_sos.received = false;
  s_sos.reference_id[0] = '\0';
  s_sos.cancel_acked = false;
  s_sos.cancel_frames_left = 0;
  s_frameReq = true;
  portEXIT_CRITICAL(&s_mux);
  buzzer_cue(CUE_SOS_SENT);
  wake_network();
  settings_sos_save_press_id(id);  // after the beep: a flash write can take a few ms
  Serial.printf("[sos] #%u raised (%s)\n", (unsigned)id, how);
}

static void cancel_sos() {
  portENTER_CRITICAL(&s_mux);
  s_sos.phase = SOS_CANCELLED;
  s_sos.cancel_frames_left = SOS_CANCEL_FRAMES;
  s_frameReq = true;
  uint32_t id = s_sos.press_id;
  portEXIT_CRITICAL(&s_mux);
  buzzer_cue(CUE_SOS_CANCELLED);
  wake_network();
  Serial.printf("[sos] #%u cancelled by the wearer\n", (unsigned)id);
}

static void sos_task(void *) {
  TickType_t last = xTaskGetTickCount();
  bool raw = false, down = false;      // down = debounced "pressed"
  uint32_t rawSince = millis();
  uint32_t pressAt = 0;
  bool pressWhileActive = false, holdDone = false;
  uint32_t taps[SOS_TAPS] = {};        // press times, oldest first
  uint8_t nTaps = 0;
  uint32_t lastBeep = 0;

  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(SOS_POLL_MS));
    uint32_t now = millis();
    bool r = digitalRead(PIN_SOS_BUTTON) == LOW;
    if (r != raw) { raw = r; rawSince = now; }
    bool active = sos_status().phase == SOS_ACTIVE;

    if (raw != down && now - rawSince >= SOS_DEBOUNCE_MS) {
      down = raw;
      if (down) {
        pressAt = now;
        pressWhileActive = active;
        holdDone = false;
        if (!active) {
          if (nTaps == SOS_TAPS) { memmove(taps, taps + 1, sizeof(taps) - sizeof(taps[0])); nTaps--; }
          taps[nTaps++] = now;
          if (nTaps == SOS_TAPS && now - taps[0] <= SOS_TAP_WINDOW_MS) {
            nTaps = 0;
            holdDone = true;  // this press must not also count as a hold
            raise_sos(now, "3 presses");
            lastBeep = now;
          }
        }
      } else if (now - pressAt >= SOS_HOLD_MS) {
        nTaps = 0;  // a long press is not a tap
      }
    }

    if (down && !holdDone) {
      uint32_t held = now - pressAt;
      if (!pressWhileActive && !active && held >= SOS_HOLD_MS) {
        holdDone = true;
        nTaps = 0;
        raise_sos(now, "hold");
        lastBeep = now;
      } else if (pressWhileActive && active && held >= SOS_CANCEL_HOLD_MS) {
        holdDone = true;
        cancel_sos();
      }
    }

    if (sos_pending() && now - lastBeep >= SOS_REMINDER_MS) {
      buzzer_cue(CUE_SOS_REMINDER);
      lastBeep = now;
    }
  }
}

void sos_begin(TaskHandle_t net_task) {
  s_netTask = net_task;
  pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);
  // Core 1 between the fast (5) and slow (3) tasks: the work per tick is one digitalRead.
  xTaskCreatePinnedToCore(sos_task, "sos", 4096, nullptr, 4, nullptr, 1);
}
