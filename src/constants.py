"""
Contracts shared between pipeline stages.

Deliberately dependency-free so it can be imported from feature extraction,
model construction, dataset loading, and the serving layer without pulling in
librosa, torch, or mediapipe.
"""

# ---------------------------------------------------------------------------
# Facial landmark geometry
# ---------------------------------------------------------------------------
#
# MediaPipe FaceMesh returns 468 landmarks for the base mesh. Enabling
# refine_landmarks adds 10 iris points (5 per eye), for 478 in total.
#
# REFINE_LANDMARKS is the single switch. Flipping it updates the landmark
# count, the flattened feature width, VisualLSTM's input layer, the zero-fill
# used for samples without video, and the serving placeholder — all at once.
# Previously these were hard-coded independently in three files and disagreed
# with what the extractor actually produced.
#
# A checkpoint trained under one setting cannot be loaded under the other.

REFINE_LANDMARKS: bool = False

N_FACE_LANDMARKS: int = 478 if REFINE_LANDMARKS else 468
LANDMARK_COORDS:  int = 3                                     # (x, y, z)
LANDMARK_DIM:     int = N_FACE_LANDMARKS * LANDMARK_COORDS    # 1404
