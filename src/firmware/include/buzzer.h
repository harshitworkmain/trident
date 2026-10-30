// Non-blocking buzzer. Driven from the fast task every 100 ms; other tasks only set requests.
// Priority, highest first (a higher source owns the pin while it is active):
//   1. SOS cue (one-shot, <= 1.1 s, 100 ms slots incl. its silent gaps, so it stays audible
//      even over a continuous alarm): sent = 2 short beeps, received = one 800 ms beep,
//      cancelled = two 400 ms beeps, reminder = one 100 ms beep (lowest cue: never interrupts
//      another cue)
//   2. local alert (latched fall / geofence breach) : continuous tone (as in v2.0)
//   3. remote "buzz" command                        : continuous tone for params.ms
//   4. server alert_level == "critical"             : 3 short beeps every 2 s, until the server
//                                                     reports another level or the state expires
#pragma once
#include <Arduino.h>

enum BuzzCue : uint8_t { CUE_SOS_REMINDER = 0, CUE_SOS_SENT, CUE_SOS_CANCELLED, CUE_SOS_RECEIVED };

void buzzer_update(uint32_t now_ms, bool local_alert);  // fast task only
void buzzer_request_ms(uint32_t ms);                    // any task
void buzzer_set_server_critical(bool critical);         // network task, on every server reply
void buzzer_cue(BuzzCue cue);                           // any task: play a one-shot SOS cue
