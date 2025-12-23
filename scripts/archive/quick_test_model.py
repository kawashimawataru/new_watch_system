"""Quick AlphaZero model test"""

import sys
from pathlib import Path
import torch
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from predictor.player.policy_value_network_pytorch import PolicyValueNet

print("🧪 AlphaZero Model Quick Test")

# Load model
model_path = Path("models/policy_value_v1.pt")
device = "mps" if torch.backends.mps.is_available() else "cpu"

model = PolicyValueNet().to(device)
checkpoint = torch.load(model_path, map_location=device)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

print(f"✅ Model loaded: {device}")

# Test on random inputs
n_tests = 100
inference_times = []
entropies = []
top1_confs = []
values = []

print(f"\n🔬 Running {n_tests} inferences...")

for i in range(n_tests):
    # Random state
    state = torch.randn(1, 512).to(device)
    
    # Measure time
    start = torch.cuda.Event(enable_timing=True) if device == "cuda" else None
    end = torch.cuda.Event(enable_timing=True) if device == "cuda" else None
    
    import time
    t0 = time.perf_counter()
    
    with torch.no_grad():
        p1_logits, p2_logits, value = model(state)
        
        # Get probabilities
        p1_probs = torch.softmax(p1_logits, dim=1)[0]
        p2_probs = torch.softmax(p2_logits, dim=1)[0]
        value_scalar = value[0, 0].item()
    
    t1 = time.perf_counter()
    inference_time = (t1 - t0) * 1000
    
    # Metrics
    inference_times.append(inference_time)
    values.append(value_scalar)
    
    # Entropy
    p1_np = p1_probs.cpu().numpy()
    entropy = -np.sum(p1_np * np.log(p1_np + 1e-10))
    entropies.append(entropy)
    
    # Top-1 confidence
    top1_conf = p1_probs.max().item()
    top1_confs.append(top1_conf)

print(f"\n📊 Results ({n_tests} samples):")
print(f"   Inference: {np.mean(inference_times):.2f}ms ± {np.std(inference_times):.2f}ms")
print(f"   Value range: [{np.min(values):.3f}, {np.max(values):.3f}]")
print(f"   Value mean: {np.mean(values):.3f} ± {np.std(values):.3f}")
print(f"   Policy entropy: {np.mean(entropies):.3f} (uniform: {np.log(32):.3f})")
print(f"   Top-1 confidence: {np.mean(top1_confs)*100:.1f}% (random: 3.1%)")
print(f"   Entropy reduction: {(1 - np.mean(entropies)/np.log(32))*100:.1f}%")

# Quality check
print(f"\n📈 Quality Assessment:")
if np.mean(top1_confs) > 0.15:
    print(f"   ✅ Strong policy preferences ({np.mean(top1_confs)*100:.1f}% >> 3.1%)")
elif np.mean(top1_confs) > 0.05:
    print(f"   ⚠️  Weak policy preferences ({np.mean(top1_confs)*100:.1f}%)")
else:
    print(f"   ❌ Nearly random policy ({np.mean(top1_confs)*100:.1f}%)")

if abs(np.mean(values)) < 0.3:
    print(f"   ✅ Value estimates balanced around 0")
else:
    print(f"   ⚠️  Value estimates biased: {np.mean(values):.3f}")

print(f"\n✅ Test complete!")
