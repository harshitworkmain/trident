#include "buzzer.h"
#include "config.h"

// 32-bit aligned values: single loads/stores are atomic on the ESP32, no lock needed.
static volatile uint32_t s_buzzUntil = 0;
static volatile uint32_t s_criticalAt = 0;  // millis() of the last "critical" reply, 0 = none
static volatile uint32_t s_cueReq = 0;      // requested cue + 1, 0 = none (swapped atomically)

// One character per 100 ms buzzer_update() slot. The leading '0' cuts a gap into a continuous
// alarm so the cue is still recognisable. Indexed by BuzzCue (also its priority).
static const char *const kCues[] = {
    "01",            // CUE_SOS_REMINDER : still trying to reach the control room
    "0110011",       // CUE_SOS_SENT     : 2 short beeps, SOS raised
    "01111001111",   // CUE_SOS_CANCELLED: 2 x 400 ms
    "011111111",     // CUE_SOS_RECEIVED : one 800 ms beep, control room has it
};

void buzzer_request_ms(uint32_t ms) {
  if (ms > BUZZ_MAX_MS) ms = BUZZ_MAX_MS;
  s_buzzUntil = millis() + ms;
}

void buzzer_set_server_critical(bool critical) {
  uint32_t now = millis();
  s_criticalAt = critical ? (now ? now : 1) : 0;
}

void buzzer_cue(BuzzCue cue) { __atomic_store_n(&s_cueReq, (uint32_t)cue + 1, __ATOMIC_SEQ_CST); }

void buzzer_update(uint32_t now_ms, bool local_alert) {
  static int s_cue = -1;  // cue being played (fast task only)
  static uint8_t s_slot = 0;

  uint32_t req = __atomic_exchange_n(&s_cueReq, 0u, __ATOMIC_SEQ_CST);
  if (req && (s_cue < 0 || (int)(req - 1) >= s_cue)) {  // a lower cue never interrupts a higher one
    s_cue = (int)(req - 1);
    s_slot = 0;
  }
  if (s_cue >= 0) {
    char c = kCues[s_cue][s_slot];
    if (c) {
      s_slot++;
      digitalWrite(PIN_BUZZER, c == '1' ? HIGH : LOW);
      return;
    }
    s_cue = -1;
  }

  bool on = local_alert || (int32_t)(s_buzzUntil - now_ms) > 0;
  uint32_t critAt = s_criticalAt;
  if (!on && critAt && now_ms - critAt < SERVER_STATE_TTL_MS) {
    uint32_t phase = now_ms % 2000;  // 200 ms on / 200 ms off x3, then a pause
    on = phase < 1000 && (phase / 200) % 2 == 0;
  }
  digitalWrite(PIN_BUZZER, on ? HIGH : LOW);
}
