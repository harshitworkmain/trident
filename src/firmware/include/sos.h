// Emergency SOS button: lets a wearer without a phone call the control room from the band.
//   raise  : hold >= 1.5 s, or 3 presses within 2 s       -> 2 short beeps
//   cancel : a new press held >= 5 s while an SOS is active -> 2 x 400 ms beeps
//   ack    : server reply {"sos": {"received": true, ...}}  -> one 800 ms beep
//   until acknowledged: a 100 ms reminder beep every 10 s
// The button is polled by its own small task (10 ms, debounced). A raise or cancel closes the
// current frame early and wakes the network task, which also stops backing off while the SOS
// is unacknowledged.
#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "frame.h"

struct SosStatus {
  SosPhase phase;              // SOS_NONE until the first press since boot
  uint32_t press_id;           // persisted counter, never repeats
  uint32_t pressed_uptime_ms;  // millis() of the raise
  bool received;               // server acknowledged the SOS
  char reference_id[24];       // "SOS-XXXXXX" from the server, "" until received
  bool cancel_acked;           // server acknowledged the cancel
  uint8_t cancel_frames_left;  // frames that still carry the cancel
};

void sos_begin(TaskHandle_t net_task);       // setup(), after the network task exists
SosStatus sos_status();                      // any task (snapshot)
bool sos_pending();                          // active and not yet acknowledged
bool sos_take_frame_request();               // fast task: true once after a raise/cancel
void sos_close(FrameData &f);                // fast task, at frame close
void sos_handle_response(JsonObjectConst s); // network task: the "sos" object of a 200 reply
