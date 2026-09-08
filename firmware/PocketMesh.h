#pragma once
#include "configuration.h"
#if HAS_TFT && defined(T_DECK)
#include <Arduino.h>
namespace PocketMesh
{
void setup();
bool send(const String &node, const String &key, const String &command, const String &args);
String takeResult();
} // namespace PocketMesh
#endif
