#!/bin/bash
# Monitor hied_mock_evidence completion and signal when done
LOG="outputs/vllm_v3_final.log"
SWEEP_DIR="outputs/sweeps/vllm_v3_fixes_evidence_20260320_034418"

while true; do
    count=$(grep -c "hied_mock_evidence.*case=" "$LOG" 2>/dev/null || echo 0)
    echo "$(date +%H:%M:%S) hied_mock_evidence: $count/50"
    
    # Check if the condition directory has predictions.json (meaning it finished)
    if [ -f "$SWEEP_DIR/hied_mock_evidence/predictions.json" ]; then
        echo "DONE: hied_mock_evidence predictions saved!"
        echo "Ready to kill sweep and start BGE-M3"
        break
    fi
    
    sleep 60
done
