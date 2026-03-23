import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import sys
from typing import Optional

class LIGMModelGate(nn.Module):
    """
    Gating mechanism to decide the activation strength of neural memory.
    Projects the input embedding into a single scalar weight (0 to 1).
    """
    def __init__(self, input_dim: int = 384):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Enforce float32 to avoid mismatch with Double/float64
        return self.net(x.float())

class LIGMModelMem(nn.Module):
    """
    Low-Rank Adaptation (LoRA) layer for embedding space.
    Learns a delta projection (B * A) scaled by the gating weight.
    """
    def __init__(self, input_dim: int = 384, rank: int = 16):
        super().__init__()
        self.rank = rank
        # Low-rank matrices: A (input -> rank), B (rank -> input)
        self.A = nn.Linear(input_dim, rank, bias=False)
        self.B = nn.Linear(rank, input_dim, bias=False)
        
        # Proper LoRA initialization: A is kaiming, B is zero
        nn.init.kaiming_uniform_(self.A.weight, a=5**0.5)
        nn.init.zeros_(self.B.weight)
        
        # Scaling factor typically used in LoRA
        self.scaling = 1.0 / rank

    def forward(self, x: torch.Tensor, w: torch.Tensor) -> torch.Tensor:
        # x is (Batch, Dim), w is (Batch, 1)
        x = x.float()
        w = w.float()
        # Apply LoRA projection
        low_rank_delta = self.B(self.A(x)) * self.scaling
        # Apply gating
        return low_rank_delta * w

class LIGMEngine:
    """
    LIGM Engine (LoRA-based Infinite Gated Memory) v3.0
    Orchestrates the neural adapter for the Synapse memory system.
    """
    def __init__(self, weights_path: str, input_dim: int = 384, rank: int = 16):
        self.weights_path = weights_path
        self.input_dim = input_dim
        self.rank = rank
        
        # Neural Modules
        self.model_gate = LIGMModelGate(input_dim)
        self.model_mem = LIGMModelMem(input_dim, rank)
        
        self.initialized = False
        self._load_weights()

    def _load_weights(self):
        """Loads weights from disk if they exist, otherwise initializes fresh."""
        if os.path.exists(self.weights_path):
            try:
                # Load on CPU by default for compatibility
                checkpoint = torch.load(self.weights_path, map_location=torch.device('cpu'))
                if 'gate' in checkpoint and 'mem' in checkpoint:
                    self.model_gate.load_state_dict(checkpoint['gate'])
                    self.model_mem.load_state_dict(checkpoint['mem'])
                self.initialized = True
            except Exception as e:
                sys.stderr.write(f"⚠️ Error loading weights: {e}. Starting with fresh weights.\n")
                self.initialized = True
        else:
            sys.stderr.write(f"ℹ️ No weights found at {self.weights_path}. System ready for first training.\n")
            self.initialized = True

    def save_weights(self, loss: float = 0.0):
        """Saves current state dicts to the specified weights path."""
        try:
            os.makedirs(os.path.dirname(self.weights_path), exist_ok=True)
            checkpoint = {
                'gate': self.model_gate.state_dict(),
                'mem': self.model_mem.state_dict(),
                'loss': loss,
                'rank': self.rank,
                'input_dim': self.input_dim
            }
            torch.save(checkpoint, self.weights_path)
            sys.stderr.write(f"💾 Neural weights saved successfully to {self.weights_path} (Loss: {loss:.8f})\n")
            self.initialized = True
        except Exception as e:
            sys.stderr.write(f"❌ Error saving weights: {e}\n")

    def transform(self, query_tensor: torch.Tensor) -> torch.Tensor:
        """
        Applies contextual warping to an input embedding.
        Formula: x_out = x_in + LIGM(x_in)
        """
        self.model_gate.eval()
        self.model_mem.eval()
        
        with torch.no_grad():
            # Handle both single vector and batches
            query_tensor = query_tensor.float()
            is_single = query_tensor.dim() == 1
            if is_single:
                query_tensor = query_tensor.unsqueeze(0)
            
            # Predict gating and delta
            w = self.model_gate(query_tensor)
            delta = self.model_mem(query_tensor, w)
            
            # Warp the space
            warped = query_tensor + delta
            
            # Return to original shape if needed
            return warped if not is_single else warped.squeeze(0)
