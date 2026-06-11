#!/bin/bash
# Usage: ./voice_query.sh [duration_seconds] [user_id]
# Example: ./voice_query.sh 5 sahil

DURATION=${1:-5}
USER_ID=${2:-sahil}
WAV_FILE=/tmp/opsagent_voice.wav
RESPONSE_FILE=/tmp/opsagent_response.json
AUDIO_FILE=/tmp/opsagent_audio.mp3

echo "🎤 Recording for ${DURATION} seconds... Speak now!"
arecord -d $DURATION -f cd $WAV_FILE 2>/dev/null
echo "✅ Recording done. Processing..."

# Send to OpsAgent
curl -s --max-time 300 -X POST http://localhost:8000/voice/ask \
  -F "file=@$WAV_FILE" \
  -F "user_id=$USER_ID" \
  > $RESPONSE_FILE

# Check for errors
if [ ! -s $RESPONSE_FILE ]; then
  echo "❌ No response from server"
  exit 1
fi

# Extract and show transcript + answer
echo ""
echo "📝 Transcript:"
cat $RESPONSE_FILE | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('transcript','N/A'))"

echo ""
echo "🤖 Agent: $(cat $RESPONSE_FILE | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('agent_used','N/A'))")"

echo ""
echo "💬 Answer:"
cat $RESPONSE_FILE | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('answer','N/A'))"

# Extract and play audio
HAS_AUDIO=$(cat $RESPONSE_FILE | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if d.get('audio_b64') else 'no')")

if [ "$HAS_AUDIO" = "yes" ]; then
  echo ""
  echo "🔊 Playing audio response..."
  cat $RESPONSE_FILE | python3 -c "
import json, base64, sys
d = json.load(sys.stdin)
audio = base64.b64decode(d['audio_b64'])
open('$AUDIO_FILE', 'wb').write(audio)
"
  ffplay -nodisp -autoexit $AUDIO_FILE 2>/dev/null
else
  echo "⚠️  No audio in response"
fi
