# Reading list — T1

**277 papers** awaiting my screening decision. 220 have a link here (79%); the rest need a library request or an author email.

Generated from `slr/out/screening.csv`. Tick as I go; the decision itself is recorded with `python3 -m slr.screen_cli --tier T1`, which saves after every record.

## The test every paper has to answer

> Multimodal emotion recognition has achieved impressive accuracy, but current systems remain insufficient for real-world healthcare and caregiving deployment due to limitations in dataset realism, real-time performance, computational efficiency, privacy, and ethical implementation.

Does this paper **support** it, **challenge** it, or neither? Neither means background, or out.

---

## 1. Read these first — 6 papers reporting both evaluation conditions

Each of these reports speaker-dependent *and* speaker-independent results for the same system. The gap between those two numbers is what ReQ5 is about (distinct from my own 66% val vs 55% test spread, where both splits were speaker-independent and the 11-point gap came from 3-actor fold variance).

Read them with one question: **how far does accuracy fall when speakers are held out?** Record both numbers.

- [ ] **R0001** · Speech Emotion Recognition From 3D Log-Mel Spectrograms With Deep Learning Network
      2019 · IEEE Access · cited 352
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/8600701/08817913.pdf)
      datasets: EMODB, IEMOCAP · **reports speaker-dependent AND independent** · no multimodal/fusion language — check EC2

- [ ] **R0032** · Speaker Normalization for Self-Supervised Speech Emotion Recognition
      2022 · ICASSP 2022 - 2022 IEEE International Conferen · cited 61
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP · **reports speaker-dependent AND independent** · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0058** · Disentanglement Network: Disentangle the Emotional Features from Acoustic Features for Speech Emotion Recognition
      2024 · cited 24
      **no open copy found** — request via library, or contact the author
      datasets: EMO-DB, IEMOCAP · **reports speaker-dependent AND independent** · no multimodal/fusion language — check EC2

- [ ] **R0217** · EEG-fNIRS Cross-Subject Emotion Recognition Based on Attention Graph Isomorphism Network and Contrastive Learning.
      2026 · Brain sciences
      [full text](https://www.mdpi.com/2076-3425/16/2/145/pdf?version=1769607998) — *publishedVersion*
      **reports speaker-dependent AND independent**

- [ ] **R0244** · Fear Recognition for Women Using a Reduced Set of Physiological Signals.
      2021 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/21/5/1587/pdf?version=1614757337) — *publishedVersion*
      **reports speaker-dependent AND independent**

- [ ] **R0266** · Modeling multiscale neural dynamics for EEG-based emotion recognition using an attentive wavelet-transformer framework.
      2026 · Frontiers in computational neuroscience
      [full text](https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2026.1775449/pdf) — *publishedVersion*
      datasets: DEAP · **reports speaker-dependent AND independent** · no multimodal/fusion language — check EC2

---

## 2. Then these — 6 papers at the edge + healthcare intersection

These sit closest to the space this thesis claims. They are the papers most likely to be raised as *hasn't this been done?*, so they are worth reading before the argument hardens rather than after.

- [ ] **R0006** · Multimodal Emotion Recognition on RAVDESS Dataset Using Transfer Learning
      2021 · Sensors · cited 158
      [full text](https://www.mdpi.com/1424-8220/21/22/7665/pdf?version=1637232590)
      datasets: RAVDESS · **edge + healthcare**

- [ ] **R0065** · Optimised knowledge distillation for efficient social media emotion recognition using DistilBERT and ALBERT
      2025 · Scientific Reports · cited 16
      [full text](https://www.nature.com/articles/s41598-025-16001-9.pdf)
      **edge + healthcare** · no multimodal/fusion language — check EC2

- [ ] **R0103** · Uncertainty-Aware Multimodal Emotion Recognition through Dirichlet Parameterization
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2602.09121v1)
      datasets: CREMA-D, MELD, RAVDESS · **edge + healthcare**

- [ ] **R0145** · Differentiable Logic Gate Networks for Low-Latency EEG Classification on Edge Devices
      2026 · Proceedings of the 39th Canadian Conference on
      [full text](https://arxiv.org/pdf/2607.18149v1)
      **edge + healthcare** · no multimodal/fusion language — check EC2

- [ ] **R0218** · MSGM: a multi-scale spatiotemporal graph Mamba for EEG emotion recognition.
      2026 · Frontiers in neuroscience
      [full text](https://public-pages-files-2025.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2026.1665145/pdf) — *publishedVersion*
      datasets: SEED · speaker-independent · **edge + healthcare**

- [ ] **R0229** · LMSA-net: a lightweight multi-scale attention network for eeg-based emotion recognition.
      2026 · Biomedical physics & engineering express
      **no open copy found** — request via library, or contact the author
      datasets: DEAP, SEED · **edge + healthcare** · no multimodal/fusion language — check EC2

---

## 3. The rest — 265 papers, grouped by Review Question

Each paper appears under the Review Question its matched search string serves. A paper matching several strings appears under the first.

### ReQ1 — What multimodal emotion recognition approaches have been proposed for healthcare and caregiving environments?

*133 papers*

- [ ] **R0002** · M3ER: Multiplicative Multimodal Emotion Recognition using Facial, Textual, and Speech Cues
      2020 · Proceedings of the AAAI Conference on Artifici · cited 256
      [full text](https://ojs.aaai.org/index.php/AAAI/article/download/5492/5348)
      datasets: IEMOCAP, MOSEI

- [ ] **R0003** · Leveraging recent advances in deep learning for audio-Visual emotion recognition
      2021 · Pattern Recognition Letters · cited 235
      [full text](https://doi.org/10.1016/j.patrec.2021.03.007)
      datasets: AFFECTNET · no results in abstract — check IC4

- [ ] **R0004** · Cross-Subject Multimodal Emotion Recognition Based on Hybrid Fusion
      2020 · IEEE Access · cited 194
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/8948470/09195813.pdf)
      datasets: DEAP · speaker-independent

- [ ] **R0005** · Audiovisual emotion recognition in wild
      2018 · Machine Vision and Applications · cited 159
      [full text](https://link.springer.com/content/pdf/10.1007/s00138-018-0960-9.pdf)
      datasets: AFEW, ENTERFACE, SAVEE · no results in abstract — check IC4

- [ ] **R0007** · Multimodal Approach of Speech Emotion Recognition Using Multi-Level Multi-Head Fusion Attention-Based Recurrent Neural Network
      2020 · IEEE Access · cited 158
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/8948470/09050806.pdf)
      datasets: IEMOCAP, MELD, MOSEI · no results in abstract — check IC4

- [ ] **R0008** · Multimodal Emotion Recognition With Transformer-Based Self Supervised Feature Fusion
      2020 · IEEE Access · cited 155
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/8948470/09206016.pdf)
      no results in abstract — check IC4

- [ ] **R0010** · Combining Facial Expressions and Electroencephalography to Enhance Emotion Recognition
      2019 · Future Internet · cited 123
      [full text](https://www.mdpi.com/1999-5903/11/5/105/pdf?version=1556781569)
      datasets: DEAP

- [ ] **R0012** · Multi-Feature Based Emotion Recognition for Video Clips
      2018 · cited 119
      [full text](https://dl.acm.org/doi/pdf/10.1145/3242969.3264989)
      datasets: AFEW

- [ ] **R0013** · A Proposal for Multimodal Emotion Recognition Using Aural Transformers and Action Units on RAVDESS Dataset
      2021 · Applied Sciences · cited 118
      [full text](https://www.mdpi.com/2076-3417/12/1/327/pdf?version=1640851558)
      datasets: RAVDESS

- [ ] **R0014** · Multimodal Emotion Recognition Based on Facial Expressions, Speech, and EEG
      2023 · IEEE Open Journal of Engineering in Medicine a · cited 112
      [full text](https://doi.org/10.1109/ojemb.2023.3240280)
      datasets: CK+, EMO-DB

- [ ] **R0016** · A Joint Cross-Attention Model for Audio-Visual Fusion in Dimensional Emotion Recognition
      2022 · 2022 IEEE/CVF Conference on Computer Vision an · cited 104
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0019** · Semantic Audiovisual Data Fusion for Automatic Emotion Recognition
      2015 · cited 87
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0021** · A Comprehensive Review of Multimodal Emotion Recognition: Techniques, Challenges, and Future Directions
      2025 · Biomimetics · cited 81
      [full text](https://www.mdpi.com/2313-7673/10/7/418/pdf?version=1751272357)

- [ ] **R0025** · MemoCMT: multimodal emotion recognition using cross-modal transformer-based feature fusion
      2025 · Scientific Reports · cited 74
      [full text](https://doi.org/10.1038/s41598-025-89202-x)
      datasets: IEMOCAP

- [ ] **R0026** · Multi-Modal Fusion Emotion Recognition Method of Speech Expression Based on Deep Learning
      2021 · Frontiers in Neurorobotics · cited 66
      [full text](https://www.frontiersin.org/articles/10.3389/fnbot.2021.697634/pdf)
      datasets: MELD, MOSI

- [ ] **R0030** · Transformer-Based Multimodal Emotional Perception for Dynamic Facial Expression Recognition in the Wild
      2023 · IEEE Transactions on Circuits and Systems for  · cited 63
      **no open copy found** — request via library, or contact the author
      datasets: AFEW

- [ ] **R0033** · Multimodal Emotion Recognition Using Transfer Learning from Speaker Recognition and BERT-Based Models
      2022 · cited 59
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP · no results in abstract — check IC4

- [ ] **R0036** · Audio–Visual Fusion for Emotion Recognition in the Valence–Arousal Space Using Joint Cross-Attention
      2023 · IEEE Transactions on Biometrics Behavior and I · cited 56
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0037** · Combining Multimodal Features within a Fusion Network for Emotion Recognition in the Wild
      2015 · cited 54
      **no open copy found** — request via library, or contact the author
      datasets: AFEW

- [ ] **R0039** · Multimodal Emotion Recognition Based on Cascaded Multichannel and Hierarchical Fusion
      2023 · Computational Intelligence and Neuroscience · cited 51
      [full text](https://downloads.hindawi.com/journals/cin/2023/9645611.pdf)
      datasets: IEMOCAP, MOSI

- [ ] **R0041** · FusionSense: Emotion Classification Using Feature Fusion of Multimodal Data and Deep Learning in a Brain-Inspired Spiking Neural Network
      2020 · Sensors · cited 50
      [full text](https://www.mdpi.com/1424-8220/20/18/5328/pdf?version=1600347654)
      speaker-independent

- [ ] **R0042** · Robust Audiovisual Emotion Recognition: Aligning Modalities, Capturing Temporal Information, and Handling Missing Features
      2022 · IEEE Transactions on Affective Computing · cited 50
      [full text](https://ieeexplore.ieee.org/ielx7/5165369/9964459/09928357.pdf)

- [ ] **R0044** · Dynamic Confidence-Aware Multi-Modal Emotion Recognition
      2023 · IEEE Transactions on Affective Computing · cited 47
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0045** · Automatic Emotion Recognition in Clinical Scenario: A Systematic Review of Methods
      2021 · IEEE Transactions on Affective Computing · cited 40
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0048** · Multi-modal Correlated Network for emotion recognition in speech
      2019 · Visual Informatics · cited 37
      [full text](https://doi.org/10.1016/j.visinf.2019.10.003)
      no results in abstract — check IC4

- [ ] **R0054** · Multimodal Transformer with Learnable Frontend and Self Attention for Emotion Recognition
      2022 · ICASSP 2022 - 2022 IEEE International Conferen · cited 28
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP · no results in abstract — check IC4

- [ ] **R0060** · Speech Emotion Recognition among Elderly Individuals using Multimodal Fusion and Transfer Learning
      2020 · Companion Publication of the 2020 Internationa · cited 21
      [full text](http://hdl.handle.net/20.500.11850/458965)

- [ ] **R0067** · Multitask Transformer for Cross-Corpus Speech Emotion Recognition
      2025 · IEEE Transactions on Affective Computing · cited 15
      **no open copy found** — request via library, or contact the author
      datasets: EMO-DB, IEMOCAP, MSP-IMPROV

- [ ] **R0072** · An Adaptive Human–Robot Interaction Framework Using Real-Time Emotion Recognition and Context-Aware Task Planning
      2025 · IEEE Access · cited 9
      [full text](https://doi.org/10.1109/access.2025.3603738)

- [ ] **R0074** · AI-Based Analysis of Student Frustration: Speech and Facial Expression Recognition
      2025 · The Electronic Journal of e-Learning · cited 7
      [full text](https://academic-publishing.org/index.php/ejel/article/download/4043/2393)
      datasets: IEMOCAP, RAVDESS

- [ ] **R0075** · Deep Emotion Recognition using Facial, Speech and Textual Cues: A Survey
      2021 · cited 6
      [full text](https://www.techrxiv.org/doi/pdf/10.36227/techrxiv.15184302.v2)
      no results in abstract — check IC4

- [ ] **R0076** · The Application and Analysis of Emotion Recognition Based on Modern Technology
      2025 · ITM Web of Conferences · cited 5
      [full text](https://www.itm-conferences.org/articles/itmconf/pdf/2025/01/itmconf_dai2024_03012.pdf)
      no multimodal/fusion language — check EC2

- [ ] **R0077** · Students' classroom Emotion Analysis Based on Intelligent Recognition
      2022 · cited 5
      **no open copy found** — request via library, or contact the author

- [ ] **R0079** · PhysioFormer: Integrating multimodal physiological signals and symbolic regression for explainable affective state prediction
      2025 · PLoS ONE · cited 4
      [full text](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0335221&type=printable)
      datasets: WESAD

- [ ] **R0083** · Analysis of the fusion of multimodal sentiment perception and physiological signals in Chinese-English cross-cultural communication: Transformer approach incorporating self-attention enhancement
      2025 · PeerJ Computer Science · cited 2
      [full text](https://peerj.com/articles/cs-2890.pdf)
      datasets: MOSEI, MOSI

- [ ] **R0089** · Multimodal Emotion Recognition and Human Computer Interaction for AI-Driven Mental Health Support (Preprint)
      2025 · cited 1
      [full text](https://s3.ca-central-1.amazonaws.com/assets.jmir.org/assets/preprints/preprint-83396-submitted.pdf) — *acceptedVersion*
      no results in abstract — check IC4

- [ ] **R0090** · User Identity Protection in Automatic Emotion Recognition through Disguised Speech
      2021 · AI · cited 1
      [full text](https://www.mdpi.com/2673-2688/2/4/38/pdf?version=1638424618) — *publishedVersion*
      no multimodal/fusion language — check EC2

- [ ] **R0092** · An interactive design solution for prenatal emotional nursing of pregnant women
      2022 · AHFE international · cited 1
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0093** · UF-AMA: A unified framework for cross-domain emotion recognition via adaptive multimodal alignment
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2606.00170v1)
      datasets: SEED · speaker-independent · no results in abstract — check IC4

- [ ] **R0094** · Adaptive Physical-Facial Representation Fusion via Subject-Invariant Cross-Modal Prompt Tuning for Video-Based Emotion Recognition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2605.05694v1)
      datasets: DEAP · speaker-independent

- [ ] **R0095** · Low Resource Multimodal Translation of Nepali Spoken Words into Emotion-Conditioned Sign Language Avatars
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2606.26107v1)

- [ ] **R0096** · From Multimodal Signals to Adaptive XR Experiences for De-escalation Training
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2604.11570v1)
      no results in abstract — check IC4

- [ ] **R0097** · Crab: Multi Layer Contrastive Supervision to Improve Speech Emotion Recognition Under Both Acted and Natural Speech Condition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.23673v1)
      datasets: IEMOCAP, MELD, MSP-PODCAST · no results in abstract — check IC4

- [ ] **R0098** · ERM-MinMaxGAP: Benchmarking and Mitigating Gender Bias in Multilingual Multimodal Speech-LLM Emotion Recognition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.21050v3)
      datasets: MELD · no results in abstract — check IC4

- [ ] **R0099** · Memory Bear AI Memory Science Engine for Multimodal Affective Intelligence: A Technical Report
      2026 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2603.22306)

- [ ] **R0100** · Team RAS in 10th ABAW Competition: Multimodal Valence and Arousal Estimation Approach
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.13056v1)
      no results in abstract — check IC4

- [ ] **R0101** · Multimodal Emotion Recognition via Bi-directional Cross-Attention and Temporal Modeling
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.11971v2)

- [ ] **R0102** · AMB-DSGDN: Adaptive modality-balanced dynamic semantic graph differential network for multimodal emotion recognition
      2026 · Expert Systems with Applications
      [full text](https://doi.org/10.1016/j.eswa.2026.132002)
      datasets: IEMOCAP, MELD · no results in abstract — check IC4

- [ ] **R0104** · AmbER$^2$: Dual Ambiguity-Aware Emotion Recognition Applied to Speech and Text
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2601.18010v1)
      datasets: IEMOCAP, MSP-PODCAST

- [ ] **R0105** · Multi-Track Multimodal Learning on iMiGUE: Micro-Gesture and Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2512.23291v1)

- [ ] **R0106** · OmniMER: Auxiliary-Enhanced LLM Adaptation for Indonesian Multimodal Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2512.19379v3)

- [ ] **R0107** · Smile on the Face, Sadness in the Eyes: Bridging the Emotion Gap with a Multimodal Dataset of Eye and Facial Behaviors
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2512.16485v1)
      no results in abstract — check IC4

- [ ] **R0108** · A Cloud-Based Cross-Modal Transformer for Emotion Recognition and Adaptive Human-Computer Interaction
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2601.14259v1)
      datasets: AFFECTNET, IEMOCAP, MELD

- [ ] **R0109** · MCN-CL: Multimodal Cross-Attention Network and Contrastive Learning for Multimodal Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2511.10892v1)
      datasets: IEMOCAP, MELD

- [ ] **R0110** · Multi-Modal Sentiment Analysis with Dynamic Attention Fusion
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2509.22729v1)

- [ ] **R0111** · Are Multimodal Foundation Models All That Is Needed for Emofake Detection?
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2509.16193v1)
      no results in abstract — check IC4

- [ ] **R0112** · MuMTAffect: A Multimodal Multitask Affective Framework for Personality and Emotion Recognition from Physiological Signals
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2509.04254v1)
      speaker-independent · no results in abstract — check IC4

- [ ] **R0113** · EmoSLLM: Parameter-Efficient Adaptation of LLMs for Speech Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2508.14130v1)
      no results in abstract — check IC4

- [ ] **R0114** · Grounding Emotion Recognition with Visual Prototypes: VEGA -- Revisiting CLIP in MERC
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2508.06564v2)
      datasets: IEMOCAP, MELD · no results in abstract — check IC4

- [ ] **R0115** · Enhancing Speech Emotion Recognition Leveraging Aligning Timestamps of ASR Transcripts and Speaker Diarization
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.19356v1)
      datasets: IEMOCAP

- [ ] **R0116** · FedMultiEmo: Real-Time Emotion Recognition via Multimodal Federated Learning
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.15470v2)
      datasets: FER2013

- [ ] **R0117** · FIRMED: A Peak-Centered Multimodal Dataset with Fine-Grained Annotation for Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.02350v3)

- [ ] **R0118** · Team RAS in 9th ABAW Competition: Multimodal Compound Expression Recognition Approach
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.02205v2)
      datasets: AFEW

- [ ] **R0119** · Facial Emotion Learning with Text-Guided Multiview Fusion via Vision-Language Model for 3D/4D Facial Expression Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.01673v1)

- [ ] **R0120** · Foundation of Affective Computing and Interaction
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2506.15497v1)
      no results in abstract — check IC4

- [ ] **R0121** · Enhancing Speech Emotion Recognition with Graph-Based Multimodal Fusion and Prosodic Features for the Speech Emotion Recognition in Naturalistic Conditions Challenge at Interspeech 2025
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2506.02088v1)

- [ ] **R0122** · Multi-modal Transfer Learning for Dynamic Facial Emotion Recognition in the Wild
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2504.21248v1)

- [ ] **R0142** · Bimodal Connection Attention Fusion for Speech Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2503.05858v3)
      datasets: IEMOCAP, MELD · no results in abstract — check IC4

- [ ] **R0143** · Smile upon the Face but Sadness in the Eyes: Emotion Recognition based on Facial Expressions and Eye Behaviors
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2411.05879v2)
      no results in abstract — check IC4

- [ ] **R0144** · Early Joint Learning of Emotion Information Makes MultiModal Model Understand You Better
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2409.18971v1)
      no results in abstract — check IC4

- [ ] **R0149** · C-GRASP: Clinically-Grounded Reasoning for Affective Signal Processing
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2601.10342v1)
      no multimodal/fusion language — check EC2

- [ ] **R0150** · EM2LDL: A Multilingual Speech Corpus for Mixed Emotion Recognition through Label Distribution Learning
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2511.20106v1)
      speaker-independent · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0151** · Emotion Recognition with Minimal Wearable Sensing: Multi-domain Feature, Hybrid Feature Selection, and Personalized vs. Generalized Ensemble Model Analysis
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2510.22498v1)

- [ ] **R0152** · Interpretable Multi-Task PINN for Emotion Recognition and EDA Prediction
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2505.18169v1)
      datasets: WESAD

- [ ] **R0153** · Improvement in Facial Emotion Recognition using Synthetic Data Generated by Diffusion Model
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2411.10863v1)
      datasets: FER2013 · no multimodal/fusion language — check EC2

- [ ] **R0154** · Design and Development of Laughter Recognition System Based on Multimodal Fusion and Deep Learning
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2407.21391v1)

- [ ] **R0155** · The PRIORI Emotion Dataset: Linking Mood to Emotion Detected In-the-Wild
      2018 · arXiv
      [full text](https://arxiv.org/pdf/1806.10658v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0156** · Explainable and Adversarially Robust Multimodal Emotion Recognition: Models, Evaluation, and a Stability Benchmark
      2026 · UA Campus Repository (The University of Arizon
      [full text](https://repository.arizona.edu/bitstream/10150/680248/1/azu_etd_22965_sip1_m.pdf)
      datasets: IEMOCAP

- [ ] **R0176** · Cross-Modal Temporal Attention for Robust Multimodal Emotion Recognition
      2025
      [full text](https://www.preprints.org/frontend/manuscript/5abea80803d5705bca6fb11bdd4cfeac/download_pub) — *acceptedVersion*
      no results in abstract — check IC4

- [ ] **R0177** · An Adaptive Multimodal Emotion Recognition Model Using Cross-Attention Mechanisms for Edge AI System
      2026
      [full text](https://www.researchsquare.com/article/rs-9347286/latest.pdf) — *acceptedVersion*

- [ ] **R0178** · Feature-level interaction and adaptive fusion model based on cross-modal attention for audiovisual emotion recognition
      2026 · Signal Image and Video Processing
      [full text](https://www.researchsquare.com/article/rs-8119217/latest.pdf)
      datasets: IEMOCAP, RAVDESS

- [ ] **R0179** · BVPEC: A Cross-modal BERT-ViT Framework for Performance Emotion Recognition from Multimodal Acting Data
      2025 · Informatica
      [full text](https://www.informatica.si/index.php/informatica/article/download/10434/5629)

- [ ] **R0180** · Deep Learning-based Facial Expression Analysis for Video Emotion Recognition and Sentiment Prediction
      2025
      [full text](https://www.researchsquare.com/article/rs-6211448/latest.pdf) — *acceptedVersion*
      datasets: AFEW, RAVDESS

- [ ] **R0181** · Enhanced Multimodal Emotion Recognition using Deep Representation Learning and Cross-Modal Feature Fusion
      2025 · International Conference on Modern Trends in E
      **no open copy found** — request via library, or contact the author

- [ ] **R0182** · EGY-MER: Establishing The First Egyptian Arabic Multimodal Emotion Recognition Dataset for Affective Computing
      2025
      [full text](https://www.researchsquare.com/article/rs-8006895/latest.pdf) — *acceptedVersion*

- [ ] **R0183** · Robust Multimodal Emotion Recognition under Temporal Asynchrony using Attention-Based CNN–Transformer Fusion
      2026
      [full text](https://doi.org/10.2139/ssrn.6544053) — *acceptedVersion*
      datasets: CREMA-D, IEMOCAP

- [ ] **R0184** · SAFE-Drive: A synergistic adaptive fusion framework for multimodal driver emotion recognition in real driving scenarios.
      2026 · Accident; analysis and prevention
      **no open copy found** — request via library, or contact the author
      speaker-independent

- [ ] **R0185** · A hierarchical multifunctional cross fusion network for emotion recognition from facial expressions and peripheral physiological signals.
      2026 · Physiological measurement
      [full text](https://iopscience.iop.org/article/10.1088/1361-6579/ae8b70/pdf) — *publishedVersion*
      no results in abstract — check IC4

- [ ] **R0186** · Adversarial Noise Isolation in Multimodal Perception: A Computational Framework Inspired by Inhibitory Control.
      2026 · Brain sciences
      [full text](https://doi.org/10.3390/brainsci16060591) — *publishedVersion*
      no results in abstract — check IC4

- [ ] **R0187** · Multimodal emotion recognition using hybrid deep feature fusion under speaker-independent evaluation
      2026 · Scientific Reports
      [full text](https://www.nature.com/articles/s41598-026-58836-w.pdf)
      datasets: CREMA-D, RAVDESS · speaker-independent

- [ ] **R0188** · Data-centric review of multimodal emotion recognition: datasets, feature extraction, data fusion and limitations
      2026 · Frontiers in Robotics and AI
      [full text](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2026.1810478/pdf)
      no results in abstract — check IC4

- [ ] **R0189** · Emotion recognition in dance therapy driven by DanceEmoNet: a deep learning model based on facial expression and pose estimation.
      2026 · Frontiers in psychology
      [full text](https://doi.org/10.3389/fpsyg.2026.1707417) — *publishedVersion*

- [ ] **R0190** · Self-Learning Multimodal Emotion Recognition Based on Multi-Scale Dilated Attention.
      2026 · Brain sciences
      [full text](https://www.mdpi.com/2076-3425/16/4/350/pdf?version=1774434937) — *publishedVersion*
      datasets: CK+, DEAP, FER2013

- [ ] **R0191** · POF cardiorespiratory sensor combined with a thermal imaging temperature sensor for multimodal emotion recognition.
      2026 · Biomedical optics express
      [full text](https://doi.org/10.1364/boe.586279) — *publishedVersion*

- [ ] **R0192** · A deep learning approach to emotionally intelligent AI for improved learning outcomes.
      2026 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-026-37750-1_reference.pdf) — *publishedVersion*
      datasets: AFFECTNET, IEMOCAP · no results in abstract — check IC4

- [ ] **R0193** · Advances in electromyography armbands for gesture recognition and multimodal fusion.
      2026 · iScience
      [full text](https://doi.org/10.1016/j.isci.2025.114517) — *publishedVersion*
      no results in abstract — check IC4

- [ ] **R0194** · Interactive graph emotion recognition based on multi-modal data enhancement.
      2026 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-34853-z_reference.pdf) — *publishedVersion*
      datasets: IEMOCAP, MELD

- [ ] **R0195** · Late Fusion Model for Emotion Recognition from Facial Expressions and Biosignals in a Dataset of Children with Autism Spectrum Disorder.
      2025 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/25/24/7485/pdf?version=1765281915) — *publishedVersion*

- [ ] **R0196** · Bridging Text and Speech for Emotion Understanding: An Explainable Multimodal Transformer Fusion Framework with Unified Audio-Text Attribution.
      2025 · Journal of Intelligence
      [full text](https://www.mdpi.com/2079-3200/13/12/159/pdf) — *publishedVersion*

- [ ] **R0197** · Intelligent assessment of English teachers' classroom language interaction and emotional behaviour based on artificial intelligence.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-20034-5.pdf) — *publishedVersion*
      datasets: MOSEI, MOSI

- [ ] **R0198** · Development of an Interactive Digital Human with Context-Sensitive Facial Expressions.
      2025 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/25/16/5117/pdf?version=1755518653) — *publishedVersion*
      datasets: AFFECTNET · no results in abstract — check IC4

- [ ] **R0199** · An ensemble classifier for emotion classification from EEG and GSR signals for autism detection.
      2025 · Computer methods and programs in biomedicine
      **no open copy found** — request via library, or contact the author

- [ ] **R0200** · Multimodal learning-based speech enhancement and separation, recent innovations, new horizons, challenges and real-world applications.
      2025 · Computers in biology and medicine
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0201** · Evaluation and analysis of visual perception using attention-enhanced computation in multimedia affective computing.
      2024 · Frontiers in neuroscience
      [full text](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2024.1449527/pdf) — *publishedVersion*
      datasets: AFFECTNET

- [ ] **R0202** · End-to-End Multimodal Emotion Recognition Based on Facial Expressions and Remote Photoplethysmography Signals.
      2024 · IEEE journal of biomedical and health informat
      **no open copy found** — request via library, or contact the author

- [ ] **R0203** · E-MFNN: an emotion-multimodal fusion neural network framework for emotion recognition.
      2024 · PeerJ. Computer science
      [full text](https://doi.org/10.7717/peerj-cs.1977) — *publishedVersion*

- [ ] **R0204** · A multimodal dynamical variational autoencoder for audiovisual speech representation learning.
      2024 · Neural networks : the official journal of the 
      [full text](https://doi.org/10.1016/j.neunet.2024.106120) — *publishedVersion*

- [ ] **R0205** · Drivers' Comprehensive Emotion Recognition Based on HAM.
      2023 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/23/19/8293/pdf?version=1696732810) — *publishedVersion*

- [ ] **R0206** · Dawn of the Transformer Era in Speech Emotion Recognition: Closing the Valence Gap.
      2023 · IEEE transactions on pattern analysis and mach
      [full text](https://arxiv.org/pdf/2203.07378) — *submittedVersion*
      datasets: IEMOCAP, MOSI, MSP-PODCAST · no results in abstract — check IC4

- [ ] **R0207** · Multi-modal emotion recognition using EEG and speech signals.
      2022 · Computers in biology and medicine
      **no open copy found** — request via library, or contact the author

- [ ] **R0208** · LGCCT: A Light Gated and Crossed Complementation Transformer for Multimodal Speech Emotion Recognition.
      2022 · Entropy (Basel, Switzerland)
      [full text](https://www.mdpi.com/1099-4300/24/7/1010/pdf?version=1658470275) — *publishedVersion*
      datasets: MOSEI

- [ ] **R0209** · Multi-Modal Residual Perceptron Network for Audio-Video Emotion Recognition.
      2021 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/21/16/5452/pdf?version=1629078133) — *publishedVersion*

- [ ] **R0210** · Mutual Correlation Attentive Factors in Dyadic Fusion Networks for Speech Emotion Recognition.
      2019 · Proceedings of the ... ACM International Confe
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MELD

- [ ] **R0211** · Lessons Learnt: Revisit Key Training Strategies for Effective Speech Emotion Recognition in the Wild
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2508.07282v2)
      no results in abstract — check IC4

- [ ] **R0232** · Emotion Recognition for Mental Health Assessment Using Transformer-Based Multimodal Learning
      2026
      [full text](https://www.researchsquare.com/article/rs-8613173/latest.pdf) — *acceptedVersion*

- [ ] **R0233** · A 1D-CNN with advanced data augmentation for robust speech emotion recognition.
      2026 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-026-56241-x_reference.pdf) — *publishedVersion*
      datasets: CREMA-D, RAVDESS, SAVEE, TESS · no multimodal/fusion language — check EC2

- [ ] **R0234** · A dual-branch deep learning framework for emotion recognition from EEG signals.
      2026 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-026-42998-8_reference.pdf) — *publishedVersion*
      datasets: WESAD

- [ ] **R0235** · A cross-domain framework for emotion and stress detection using WESAD, SCIENTISST-MOVE, and DREAMER datasets.
      2025 · Frontiers in bioengineering and biotechnology
      [full text](https://public-pages-files-2025.frontiersin.org/journals/bioengineering-and-biotechnology/articles/10.3389/fbioe.2025.1659002/pdf) — *publishedVersion*
      datasets: WESAD · no multimodal/fusion language — check EC2

- [ ] **R0236** · An Explainable Framework for Mental Health Monitoring Using Lightweight and Privacy-Preserving Federated Facial Emotion Recognition.
      2025 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/25/23/7320/pdf) — *publishedVersion*
      datasets: FER2013 · no multimodal/fusion language — check EC2

- [ ] **R0237** · Fine-Tuning a Pretrained CNN Combined with Self-Attention for Speech Emotion Recognition.
      2025 · Annual International Conference of the IEEE En
      **no open copy found** — request via library, or contact the author
      speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0238** · AI-based emotion recognition in dementia through facial expression: A scoping review.
      2026 · Ageing research reviews
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2

- [ ] **R0239** · FedSER-XAI: PSO-optimized multi-stream cross-attention transformer with graph features for explainable federated speech emotion recognition.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-28686-z_reference.pdf) — *publishedVersion*
      datasets: CREMA-D, EMODB, SAVEE · no multimodal/fusion language — check EC2

- [ ] **R0240** · Multilingual identification of nuanced dimensions of hope speech in social media texts.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-10683-x.pdf) — *publishedVersion*
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0241** · Emotion-Aware RoBERTa enhanced with emotion-specific attention and TF-IDF gating for fine-grained emotion recognition.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-99515-6.pdf) — *publishedVersion*
      no multimodal/fusion language — check EC2

- [ ] **R0242** · Enhancing EEG-Based Emotion Detection with Hybrid Models: Insights from DEAP Dataset Applications.
      2025 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/25/6/1827/pdf?version=1741967794) — *publishedVersion*
      datasets: DEAP · no multimodal/fusion language — check EC2

- [ ] **R0243** · EEG-based emotion charting for Parkinson's disease patients using Convolutional Recurrent Neural Networks and cross dataset learning.
      2022 · Computers in biology and medicine
      **no open copy found** — request via library, or contact the author
      datasets: SEED · no multimodal/fusion language — check EC2

- [ ] **R0245** · Evaluating Open-Source Vision Language Models for Facial Emotion Recognition against Traditional Deep Learning Models
      2025 · EAI Endorsed Transactions on AI and Robotics, 
      [full text](https://arxiv.org/pdf/2508.13524v1)
      datasets: FER-2013 · no multimodal/fusion language — check EC2

- [ ] **R0250** · Robust Multimodal Emotion Recognition with Interpretable Fusion
      2026 · Figshare
      [full text](https://doi.org/10.6084/m9.figshare.31567024)
      datasets: MOSEI, SEED

- [ ] **R0256** · ViMER-Tri: A Trimodal Vietnamese Emotion Recognition System with Adaptive Missing-Modality Fusion
      2025
      **no open copy found** — request via library, or contact the author

- [ ] **R0257** · A Study on Multimodal Emotion Recognition of “Chinese Stories” Among Foreign Audiences Using Deep Learning Technology
      2026
      [full text](https://doi.org/10.1145/3802607.3802622)
      no results in abstract — check IC4

- [ ] **R0262** · Multimodal Smart Stress Analyzer Using Facial Expression and Speech Emotion Recognition
      2026 · INTERANTIONAL JOURNAL OF SCIENTIFIC RESEARCH I
      **no open copy found** — request via library, or contact the author
      datasets: CREMA-D, RAVDESS

- [ ] **R0263** · A Systematic Literature Review on Deep Learning Based Multimodal Facial Expression Recognition: Trends, Gaps, and Future Opportunities
      2025
      **no open copy found** — request via library, or contact the author
      datasets: AFFECTNET, CK+ · no results in abstract — check IC4

- [ ] **R0264** · Deep Emotion Recognition in Dynamic Data using Facial, Speech and Textual Cues: A Survey
      2021
      [full text](https://www.techrxiv.org/articles/preprint/Deep_Emotion_Recognition_in_Dynamic_Data_using_Facial_Speech_and_Textual_Cues_A_Survey/15184302/1/files/29162985.pdf)
      no results in abstract — check IC4


### ReQ2 — Which speech, facial and behavioural features are most commonly used for multimodal emotion recognition?

*1 papers*

- [ ] **R0063** · Generalisation and robustness investigation for facial and speech emotion recognition using bio-inspired spiking neural networks
      2021 · Soft Computing · cited 17
      [full text](https://link.springer.com/content/pdf/10.1007/s00500-020-05501-7.pdf)
      speaker-independent · no multimodal/fusion language — check EC2


### ReQ4 — Which datasets are most frequently used, and how representative are they of real-world healthcare settings?

*51 papers*

- [ ] **R0009** · Cross corpus multi-lingual speech emotion recognition using ensemble learning
      2021 · Complex & Intelligent Systems · cited 139
      [full text](https://link.springer.com/content/pdf/10.1007/s40747-020-00250-4.pdf)
      no multimodal/fusion language — check EC2

- [ ] **R0015** · Cross Lingual Speech Emotion Recognition: Urdu vs. Western Languages
      2018 · cited 108
      [full text](https://arxiv.org/pdf/1812.10411v2) — *submittedVersion*
      no multimodal/fusion language — check EC2

- [ ] **R0018** · Improving Cross-Corpus Speech Emotion Recognition with Adversarial Discriminative Domain Generalization (ADDoG)
      2019 · IEEE Transactions on Affective Computing · cited 95
      [full text](https://arxiv.org/pdf/1903.12094)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0020** · Cross-Corpus Acoustic Emotion Recognition with Multi-Task Learning: Seeking Common Ground While Preserving Differences
      2017 · IEEE Transactions on Affective Computing · cited 84
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0024** · Towards Speech Emotion Recognition “in the Wild” Using Aggregated Corpora and Deep Multi-Task Learning
      2017 · cited 77
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0027** · Self Supervised Adversarial Domain Adaptation for Cross-Corpus and Cross-Language Speech Emotion Recognition
      2022 · IEEE Transactions on Affective Computing · cited 66
      [full text](https://opus.bibliothek.uni-augsburg.de/opus4/files/108969/108969.pdf)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0040** · CROSS-CORPUS EEG-BASED EMOTION RECOGNITION
      2018 · cited 51
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0047** · Multitask Learning From Augmented Auxiliary Data for Improving Speech Emotion Recognition
      2022 · IEEE Transactions on Affective Computing · cited 39
      [full text](https://opus.bibliothek.uni-augsburg.de/opus4/files/112079/112079.pdf)
      datasets: EMODB, IEMOCAP, MSP-IMPROV · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0050** · Fusing Visual Attention CNN and Bag of Visual Words for Cross-Corpus Speech Emotion Recognition
      2020 · Sensors · cited 35
      [full text](https://www.mdpi.com/1424-8220/20/19/5559/pdf?version=1601296315)
      datasets: EMODB, RAVDESS, SAVEE

- [ ] **R0051** · A Cross-Corpus Study on Speech Emotion Recognition
      2019 · 2019 IEEE Automatic Speech Recognition and Und · cited 31
      [full text](https://arxiv.org/pdf/2207.02104)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0052** · Adversarial Domain Generalized Transformer for Cross-Corpus Speech Emotion Recognition
      2023 · IEEE Transactions on Affective Computing · cited 30
      [full text](https://ieeexplore.ieee.org/ielx7/5165369/5520654/10168224.pdf)
      no results in abstract — check IC4

- [ ] **R0053** · Cross Corpus Speech Emotion Classification- An Effective Transfer Learning Technique.
      2018 · arXiv (Cornell University) · cited 28
      [full text](http://export.arxiv.org/pdf/1801.06353)
      no multimodal/fusion language — check EC2

- [ ] **R0055** · Within and cross-corpus speech emotion recognition using latent topic model-based features
      2015 · EURASIP Journal on Audio Speech and Music Proc · cited 27
      [full text](https://asmp-eurasipjournals.springeropen.com/counter/pdf/10.1186/s13636-014-0049-y)
      no multimodal/fusion language — check EC2

- [ ] **R0056** · Improved Cross-Corpus Speech Emotion Recognition Using Deep Local Domain Adaptation
      2023 · Chinese Journal of Electronics · cited 25
      [full text](https://ieeexplore.ieee.org/ielx7/9970761/10124650/10124696.pdf)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0061** · Multi-Task Semi-Supervised Adversarial Autoencoding for Speech Emotion Recognition
      2020 · IEEE Transactions on Affective Computing · cited 21
      [full text](https://arxiv.org/pdf/1907.06078)
      no multimodal/fusion language — check EC2

- [ ] **R0062** · A Study on Cross-Corpus Speech Emotion Recognition and Data Augmentation
      2021 · 2021 IEEE Automatic Speech Recognition and Und · cited 19
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2

- [ ] **R0064** · Cross-Corpus Speech Emotion Recognition Based on Joint Transfer Subspace Learning and Regression
      2021 · IEEE Transactions on Cognitive and Development · cited 17
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0066** · Cross Lingual Cross Corpus Speech Emotion Recognition
      2020 · arXiv (Cornell University) · cited 15
      [full text](https://arxiv.org/pdf/2003.07996)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0069** · Domain Generalization with Triplet Network for Cross-Corpus Speech Emotion Recognition
      2021 · cited 12
      **no open copy found** — request via library, or contact the author
      no multimodal/fusion language — check EC2

- [ ] **R0073** · A Performance Benchmarking Review of Transformers for Speaker-Independent Speech Emotion Recognition
      2025 · International Journal of Neural Systems · cited 9
      [full text](https://doi.org/10.1142/s0129065725300013)
      speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0157** · Boundary-aware Prototype-driven Adversarial Alignment for Cross-Corpus EEG Emotion Recognition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.26713v1)
      datasets: SEED · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0158** · Test-Time Adaptation for Speech Emotion Recognition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2601.16240v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0159** · E^2-LLM: Bridging Neural Signals and Interpretable Affective Analysis
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2601.07877v1)

- [ ] **R0160** · Distilled HuBERT for Mobile Speech Emotion Recognition: A Cross-Corpus Validation Study
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2512.23435v2)
      datasets: CREMA-D, IEMOCAP, RAVDESS · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0161** · Cross-Corpus Validation of Speech Emotion Recognition in Urdu using Domain-Knowledge Acoustic Features
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2510.26823v1)
      no multimodal/fusion language — check EC2

- [ ] **R0162** · Emotion-Disentangled Embedding Alignment for Noise-Robust and Cross-Corpus Speech Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2510.09072v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0163** · Speech-Based Depressive Mood Detection in the Presence of Multiple Sclerosis: A Cross-Corpus and Cross-Lingual Study
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2508.18092v1)
      no multimodal/fusion language — check EC2

- [ ] **R0164** · THAI Speech Emotion Recognition (THAI-SER) corpus
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.09618v1)
      no multimodal/fusion language — check EC2

- [ ] **R0165** · Developing a High-performance Framework for Speech Emotion Recognition in Naturalistic Conditions Challenge for Emotional Attribute Prediction
      2025 · Accepeted to Interspeech2025
      [full text](https://arxiv.org/pdf/2506.10930v1)
      datasets: MSP-PODCAST · no results in abstract — check IC4

- [ ] **R0166** · Developing a Top-tier Framework in Naturalistic Conditions Challenge for Categorized Emotion Prediction: From Speech Foundation Models and Learning Objective to Data Augmentation and Engineering Choices
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2505.22133v2)
      no multimodal/fusion language — check EC2

- [ ] **R0167** · Is It Still Fair? Investigating Gender Fairness in Cross-Corpus Speech Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2501.00995v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0168** · A Cross-Corpus Speech Emotion Recognition Method Based on Supervised Contrastive Learning
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2411.19803v1)
      datasets: IEMOCAP · no multimodal/fusion language — check EC2

- [ ] **R0169** · ParaLBench: A Large-Scale Benchmark for Computational Paralinguistics over Acoustic Foundation Models
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2411.09349v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0170** · EEG-SCMM: Soft Contrastive Masked Modeling for Cross-Corpus EEG-Based Emotion Recognition
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2408.09186v2)
      datasets: DEAP, SEED · no multimodal/fusion language — check EC2

- [ ] **R0171** · Emotion-LLaMA: Multimodal Emotion Recognition and Reasoning with Instruction Tuning
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2406.11161v2)

- [ ] **R0172** · What Does it Take to Generalize SER Model Across Datasets? A Comprehensive Benchmark
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2406.09933v1)
      speaker-independent · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0173** · Joint Contrastive Learning with Feature Alignment for Cross-Corpus EEG-based Emotion Recognition
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2404.09559v1)
      no multimodal/fusion language — check EC2

- [ ] **R0174** · EMOVOME: A Dataset for Emotion Recognition in Spontaneous Real-Life Speech
      2024 · arXiv
      [full text](https://arxiv.org/pdf/2403.02167v3)
      datasets: IEMOCAP, RAVDESS · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0175** · DSNet: Disentangled Siamese Network with Neutral Calibration for Speech Emotion Recognition
      2023 · arXiv
      [full text](https://arxiv.org/pdf/2312.15593v1)
      speaker-independent · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0265** · EEG-based emotion recognition using phase-space reconstruction with Poincaré sections: a study on the AMIGOS dataset.
      2026 · Frontiers in human neuroscience
      [full text](https://doi.org/10.3389/fnhum.2026.1660402) — *publishedVersion*
      datasets: DEAP · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0267** · FedEmoNet: Privacy-preserving federated learning with TCN-Transformer fusion for cross-corpus speech emotion recognition.
      2026 · PloS one
      [full text](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0342953&type=printable) — *publishedVersion*
      datasets: CREMA-D, EMODB, RAVDESS · speaker-independent

- [ ] **R0268** · Data-Centric AI for EEG-Based Emotion Recognition: Noise Filtering and Augmentation Strategies.
      2025 · Bioengineering (Basel, Switzerland)
      [full text](https://www.mdpi.com/2306-5354/12/11/1264/pdf?version=1763473217) — *publishedVersion*
      datasets: SEED · no multimodal/fusion language — check EC2

- [ ] **R0269** · Objective Emotion Assessment Using a Triple Attention Network for an EEG-Based Brain-Computer Interface.
      2025 · Brain sciences
      [full text](https://www.mdpi.com/2076-3425/15/11/1167/pdf?version=1761754904) — *publishedVersion*
      datasets: DEAP, SEED · speaker-independent

- [ ] **R0270** · Attention-Based Transfer Enhancement Network for Cross-Corpus EEG Emotion Recognition.
      2025 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/25/18/5718/pdf?version=1757748857) — *publishedVersion*
      datasets: SEED · no multimodal/fusion language — check EC2

- [ ] **R0271** · EmoTrans attention based emotion recognition using EEG signals and facial analysis with expert validation.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-98404-2.pdf) — *publishedVersion*
      datasets: DEAP · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0272** · Cross-Corpus Speech Emotion Recognition Based on Transfer Learning and Multi-Loss Dynamic Adjustment.
      2022 · Computational intelligence and neuroscience
      [full text](https://downloads.hindawi.com/journals/cin/2022/5019384.pdf) — *publishedVersion*
      datasets: ENTERFACE · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0273** · Cross-Language Speech Emotion Recognition Using Bag-of-Word Representations, Domain Adaptation, and Data Augmentation.
      2022 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/22/17/6445/pdf?version=1661831040) — *publishedVersion*
      no multimodal/fusion language — check EC2

- [ ] **R0274** · Human and machine validation of 14 databases of dynamic facial expressions.
      2021 · Behavior research methods
      [full text](https://link.springer.com/content/pdf/10.3758/s13428-020-01443-y.pdf) — *publishedVersion*
      no multimodal/fusion language — check EC2

- [ ] **R0275** · Speaker-sensitive emotion recognition via ranking: Studies on acted and spontaneous speech☆.
      2015 · Computer speech & language
      [full text](https://www.ncbi.nlm.nih.gov/pmc/articles/4240517) — *submittedVersion*
      speaker-independent

- [ ] **R0276** · Emotion Recognition Using Acoustic Features and Deep Learning: A Speaker-Independent Study
      2026 · Signals
      [full text](https://www.mdpi.com/2624-6120/7/4/69/pdf?version=1784014231) — *publishedVersion*
      speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0277** · Parameter Efficient Finetuning for Speech Emotion Recognition and Domain Adaptation
      2024 · ICASSP 2024 - 2024 IEEE International Conferen
      [full text](https://arxiv.org/pdf/2402.11747v1)
      no multimodal/fusion language — check EC2 · no results in abstract — check IC4


### ReQ6 — What challenges remain regarding real-time deployment, computational efficiency, robustness, privacy, interpretability and ethical implementation?

*80 papers*

- [ ] **R0011** · From Neural Networks to Emotional Networks: A Systematic Review of EEG-Based Emotion Recognition in Cognitive Neuroscience and Real-World Applications
      2025 · Brain Sciences · cited 122
      [full text](https://www.mdpi.com/2076-3425/15/3/220/pdf?version=1740057185)

- [ ] **R0017** · Transformer-Based Self-Supervised Multimodal Representation Learning for Wearable Emotion Recognition
      2023 · IEEE Transactions on Affective Computing · cited 97
      [full text](https://hal.science/hal-04051433v1/document)
      no results in abstract — check IC4

- [ ] **R0022** · Contrastive Learning Based Modality-Invariant Feature Acquisition for Robust Multimodal Emotion Recognition With Missing Modalities
      2024 · IEEE Transactions on Affective Computing · cited 80
      **no open copy found** — request via library, or contact the author

- [ ] **R0023** · FedMultimodal: A Benchmark for Multimodal Federated Learning
      2023 · arXiv · cited 77
      [full text](https://dl.acm.org/doi/pdf/10.1145/3580305.3599825)
      no results in abstract — check IC4

- [ ] **R0028** · Enhanced semi-supervised learning for multimodal emotion recognition
      2016 · cited 65
      [full text](https://opus.bibliothek.uni-augsburg.de/opus4/files/71513/71513.pdf)

- [ ] **R0029** · A Generative Random Modality Dropout Framework for Robust Multimodal Emotion Recognition
      2025 · IEEE Intelligent Systems · cited 65
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4 · **no abstract** — title-only

- [ ] **R0031** · EdgeRNN: A Compact Speech Recognition Network With Spatio-Temporal Features for Edge Computing
      2020 · IEEE Access · cited 62
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/8948470/09081948.pdf)
      datasets: IEMOCAP · no multimodal/fusion language — check EC2

- [ ] **R0034** · Exploiting Modality-Invariant Feature for Robust Multimodal Emotion Recognition with Missing Modalities
      2023 · ICASSP 2023 - 2023 IEEE International Conferen · cited 57
      [full text](https://arxiv.org/pdf/2210.15359)
      datasets: IEMOCAP · no results in abstract — check IC4

- [ ] **R0035** · Enhancing emotion recognition using multimodal fusion of physiological, environmental, personal data
      2024 · Expert Systems with Applications · cited 57
      [full text](https://doi.org/10.1016/j.eswa.2024.123723)

- [ ] **R0038** · Complementary Fusion of Multi-Features and Multi-Modalities in Sentiment Analysis
      2019 · arXiv (Cornell University) · cited 53
      [full text](https://arxiv.org/pdf/1904.08138)
      datasets: IEMOCAP, MOSEI, MOSI

- [ ] **R0043** · A Resource Efficient Integer-Arithmetic-Only FPGA-Based CNN Accelerator for Real-Time Facial Emotion Recognition
      2021 · IEEE Access · cited 48
      [full text](https://ieeexplore.ieee.org/ielx7/6287639/9312710/09493194.pdf)
      no multimodal/fusion language — check EC2

- [ ] **R0046** · Emotion recognition based on multimodal physiological electrical signals
      2025 · Frontiers in Neuroscience · cited 39
      [full text](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2025.1512799/pdf)
      datasets: DEAP

- [ ] **R0049** · Factors in Emotion Recognition With Deep Learning Models Using Speech and Text on Multiple Corpora
      2022 · IEEE Signal Processing Letters · cited 37
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP · no results in abstract — check IC4

- [ ] **R0057** · A Hybrid Multimodal Emotion Recognition Framework for UX Evaluation Using Generalized Mixture Functions
      2023 · Sensors · cited 24
      [full text](https://www.mdpi.com/1424-8220/23/9/4373/pdf?version=1683094089)

- [ ] **R0059** · Learning Robust Multi-Modal Representation for Multi-Label Emotion Recognition via Adversarial Masking and Perturbation
      2023 · cited 22
      [full text](https://dl.acm.org/doi/pdf/10.1145/3543507.3583258)
      datasets: MOSEI · no results in abstract — check IC4

- [ ] **R0068** · Multimodal Multitask Emotion Recognition using Images, Texts and Tags
      2019 · cited 13
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0070** · Multimodal Emotion Recognition with Vision-language Prompting and Modality Dropout
      2024 · Proceedings of the 2nd International Workshop  · cited 11
      [full text](https://arxiv.org/pdf/2409.07078v1)

- [ ] **R0071** · Causal Inference for Modality Debiasing in Multimodal Emotion Recognition
      2024 · Applied Sciences · cited 10
      [full text](https://doi.org/10.3390/app142311397)
      datasets: IEMOCAP, MOSEI

- [ ] **R0078** · Hardness-Aware Dynamic Curriculum Learning for Robust Multimodal Emotion Recognition with Missing Modalities
      2025 · arXiv · cited 4
      [full text](https://arxiv.org/pdf/2508.06800v2)
      no results in abstract — check IC4

- [ ] **R0080** · Harnessing Haptic Technology for Real-Time Emotion Detection
      2025 · IEEE Sensors Letters · cited 4
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0081** · Multimodal emotion recognition from complete modality to missing modality based on text, audio, and visual: A review
      2026 · Engineering Applications of Artificial Intelli · cited 3
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4 · **no abstract** — title-only

- [ ] **R0082** · ROSA: A Robust Self-Adaptive Model for Multimodal Emotion Recognition With Uncertain Missing Modalities
      2025 · IEEE Transactions on Multimedia · cited 3
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0084** · Spatiotemporal multimodal emotion recognition using Temporal video sequences and pose features for child emotion classification
      2025 · Scientific Reports · cited 2
      [full text](https://www.nature.com/articles/s41598-025-25813-8.pdf)

- [ ] **R0085** · A Cross-Modal Adaptive Masked Autoencoder for Decoding Emotions With Multimodal Data
      2024 · IEEE Transactions on Computational Social Syst · cited 2
      **no open copy found** — request via library, or contact the author
      datasets: DEAP, SEED · no results in abstract — check IC4

- [ ] **R0086** · Leveraging Retrieval Augment Approach for Multimodal Emotion Recognition Under Missing Modalities
      2024 · arXiv (Cornell University) · cited 1
      [full text](https://arxiv.org/pdf/2410.02804)
      no results in abstract — check IC4

- [ ] **R0087** · Multimodal Emotion Recognition with Missing Modality via a Unified Multi-task Pre-training Framework
      2025 · Proceedings of the 33rd ACM International Conf · cited 1
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0088** · Progressive Learning Framework With Missing Modality Reconstruction for Multimodal Emotion Recognition
      2025 · IEEE Transactions on Audio Speech and Language · cited 1
      [full text](https://ieeexplore.ieee.org/ielam/10723155/11302005/11278755-aam.pdf)
      datasets: IEMOCAP, MOSI, MSP-IMPROV

- [ ] **R0091** · A Novel Decoupled Prototype Completion Network for Incomplete Multimodal Emotion Recognition
      2024 · cited 1
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MOSI · no results in abstract — check IC4

- [ ] **R0123** · BioKD: Selective Physiology-to-Video Knowledge Distillation via Reliability Gate for Emotion Recognition
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2608.06023v1)
      datasets: DEAP · speaker-independent · no results in abstract — check IC4

- [ ] **R0124** · SpEmoC: A Balanced Speaker-Segment Multimodal Emotion Benchmark
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2607.18109v1)
      no results in abstract — check IC4

- [ ] **R0125** · EmoEUS: Uncertainty Supervision for Multimodal Emotion Recognition in Conversation
      2026 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2607.18336)
      datasets: IEMOCAP, MELD · no results in abstract — check IC4

- [ ] **R0126** · State-Anchored Complete-View Distillation for Robust Conversational Multimodal Emotion Recognition
      2026 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2605.29590)
      datasets: IEMOCAP, MELD, MOSEI · no results in abstract — check IC4

- [ ] **R0127** · EmoS: A High-Fidelity Multimodal Benchmark for Fine-grained Streaming Emotional Understanding
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2605.08847v1)
      no results in abstract — check IC4

- [ ] **R0128** · Appraisal Dimensions Generalise Better than Emotion Labels for Cross-Age Affect Recognition in AI-Assisted Healthcare
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2604.27938v2)

- [ ] **R0129** · C$^2$MOE: Consistency and Complementarity-guided Mixture of Experts for Incomplete Multimodal Emotion Learning
      2026 · arXiv (Cornell University)
      [full text](https://doi.org/10.1145/3805622.3810726)
      no results in abstract — check IC4

- [ ] **R0130** · AffectAgent: Collaborative Multi-Agent Reasoning for Retrieval-Augmented Multimodal Emotion Recognition
      2026 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2604.12735)
      no results in abstract — check IC4

- [ ] **R0131** · MissBench: Benchmarking Multimodal Affective Analysis under Imbalanced Missing Modalities
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.09874v1)
      no results in abstract — check IC4

- [ ] **R0132** · Solution to the 10th ABAW Expression Recognition Challenge: A Robust Multimodal Framework with Safe Cross-Attention and Modality Dropout
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2603.08034v1)

- [ ] **R0133** · Federated Dialogue-Semantic Diffusion for Emotion Recognition under Incomplete Modalities
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2511.00344)
      datasets: IEMOCAP · no results in abstract — check IC4

- [ ] **R0134** · Contribution-Guided Asymmetric Learning for Robust Multimodal Fusion under Imbalance and Noise
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2510.26289v2)
      datasets: CREMA-D

- [ ] **R0135** · Towards an Adaptive Social Game-Playing Robot: An Offline Reinforcement Learning-Based Framework
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2509.16858v2)
      no results in abstract — check IC4

- [ ] **R0136** · A Robust Incomplete Multimodal Low-Rank Adaptation Approach for Emotion Recognition
      2025 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2507.11202)

- [ ] **R0137** · CLEP-DG: Contrastive Learning for Speech Emotion Domain Generalization via Soft Prompt Tuning
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2507.04048v1)
      no results in abstract — check IC4

- [ ] **R0138** · GSDNet: Revisiting Incomplete Multimodal-Diffusion from Graph Spectrum Perspective for Conversation Emotion Recognition
      2025 · arXiv (Cornell University)
      [full text](https://arxiv.org/pdf/2506.12325)
      no results in abstract — check IC4

- [ ] **R0139** · EmotionTalk: An Interactive Chinese Multimodal Emotion Dataset With Rich Annotations
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2505.23018v3)
      no results in abstract — check IC4

- [ ] **R0140** · RoHyDR: Robust Hybrid Diffusion Recovery for Incomplete Multimodal Emotion Recognition
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2505.17501v1)
      no results in abstract — check IC4

- [ ] **R0141** · Towards Robust Multimodal Physiological Foundation Models: Handling Arbitrary Missing Modalities
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2504.19596v3)
      no results in abstract — check IC4

- [ ] **R0146** · Facial Emotion Recognition on FER-2013 using an EfficientNetB2-Based Approach
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2601.18228v1)
      datasets: FER-2013 · no multimodal/fusion language — check EC2

- [ ] **R0147** · Rethinking Facial Expression Recognition in the Era of Multimodal Large Language Models: Benchmark, Datasets, and Beyond
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2511.00389v1)
      no results in abstract — check IC4

- [ ] **R0148** · Compressing Quaternion Convolutional Neural Networks for Audio Classification
      2025 · arXiv
      [full text](https://arxiv.org/pdf/2510.21388v1)
      datasets: RAVDESS · no multimodal/fusion language — check EC2 · no results in abstract — check IC4

- [ ] **R0212** · Contrastive Learning–Based Modality-Aware Multimodal Emotion Recognition
      2026
      [full text](https://doi.org/10.2139/ssrn.6414581) — *acceptedVersion*
      datasets: IEMOCAP, RAVDESS

- [ ] **R0213** · Robust multimodal emotion recognition under missing and incomplete data with cross-modal regeneration
      2026 · Empathic Computing
      [full text](https://oss.sciexplor.com/manuscript/980/publish/EC_202610.pdf)

- [ ] **R0214** · Incomplete Multimodal Probability Flow Recovery for Emotion Recognition
      2026 · IEEE Transactions on Pattern Analysis and Mach
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0215** · A GPTAssisted Multi Modal Emotion Intelligence Framework for Mental Health Predictive Analytics using Physiological Signals.
      2026 · IEEE journal of biomedical and health informat
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0216** · Enhanced graph attention network by integrating Long Short-Term Memory for artificial emotion representation in multi-modality datasets.
      2026 · PloS one
      [full text](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0339946&type=printable) — *publishedVersion*
      datasets: MOSEI, RAVDESS

- [ ] **R0219** · "RaagaDhvani: A novel augmented multi-feature dataset: Advancing emotion recognition in Carnatic music with multimodal features and hybrid deep learning".
      2026 · Data in brief
      [full text](https://doi.org/10.1016/j.dib.2025.112364) — *publishedVersion*
      datasets: EMODB, IEMOCAP, RAVDESS, SAVEE · no results in abstract — check IC4

- [ ] **R0220** · Enhancing emotion recognition in virtual reality: a multimodal dataset and a temporal emotion detector.
      2025 · Frontiers in psychology
      [full text](https://public-pages-files-2025.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1709943/pdf) — *publishedVersion*

- [ ] **R0221** · Investigating the capabilities of large vision language models in dog emotion recognition.
      2025 · Scientific reports
      [full text](https://www.nature.com/articles/s41598-025-25199-7.pdf) — *publishedVersion*

- [ ] **R0222** · Cross-modal alignment and fusion of EEG-visual based on mixed attention mechanism for emotion recognition.
      2025 · Cognitive neurodynamics
      [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12596239/) — *acceptedVersion*
      datasets: SEED · speaker-independent

- [ ] **R0223** · Cross-Subject EEG Emotion Recognition Using SSA-EMS Algorithm for Feature Extraction.
      2025 · Entropy (Basel, Switzerland)
      [full text](https://www.mdpi.com/1099-4300/27/9/986/pdf?version=1758436588) — *publishedVersion*
      datasets: SEED · speaker-independent

- [ ] **R0224** · EmoShiftNet: a shift-aware multi-task learning framework with fusion strategies for emotion recognition in multi-party conversations.
      2025 · Frontiers in artificial intelligence
      [full text](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1618698/pdf) — *publishedVersion*
      datasets: MELD

- [ ] **R0225** · Stress and Emotion Open Access Data: A Review on Datasets, Modalities, Methods, Challenges, and Future Research Perspectives.
      2025 · Journal of healthcare informatics research
      [full text](https://link.springer.com/content/pdf/10.1007/s41666-025-00200-0.pdf) — *publishedVersion*
      no results in abstract — check IC4

- [ ] **R0226** · Context-Aware Emotion Recognition in the Wild Using Spatio-Temporal and Temporal-Pyramid Models.
      2021 · Sensors (Basel, Switzerland)
      [full text](https://www.mdpi.com/1424-8220/21/7/2344/pdf?version=1617937431) — *publishedVersion*
      datasets: AFEW

- [ ] **R0227** · Relational graph-driven differential denoising and diffusion attention fusion for multimodal conversation emotion recognition
      2026 · neurocomputing2026
      [full text](https://arxiv.org/pdf/2603.25752v1)
      no results in abstract — check IC4

- [ ] **R0228** · Analysis of the generalization ability of graph neural networks in cross-subject EEG emotion recognition.
      2026 · Neurological sciences : official journal of th
      **no open copy found** — request via library, or contact the author
      datasets: DEAP, SEED · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0230** · Speech Emotion Recognition using Attention-based LSTM-Network with Residual Connection
      2026 · arXiv
      [full text](https://arxiv.org/pdf/2606.03359v1)
      datasets: RAVDESS · speaker-independent · no multimodal/fusion language — check EC2

- [ ] **R0231** · EEG Emotion Copilot: Optimizing lightweight LLMs for emotional EEG interpretation with assisted medical record generation.
      2025 · Neural networks : the official journal of the 
      [full text](https://arxiv.org/pdf/2410.00166v3)
      no multimodal/fusion language — check EC2

- [ ] **R0246** · Expanding Intra-modal and Compressing Inter-modal Embedding Space for Incomplete Multimodal Emotion Recognition
      2026 · IEEE Transactions on Circuits and Systems for 
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0247** · CRNet: Context-Guided Recovering Network for Incomplete Multimodal Emotion Recognition in Conversation
      2026 · IEEE Transactions on Multimedia
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0248** · Context-Aware Dynamic Graph Learning for Multimodal Emotion Recognition with Missing Modalities
      2026
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MELD · no results in abstract — check IC4

- [ ] **R0249** · DGSDNet: Dual-Graph Spectral Diffusion Network for Incomplete Multimodal Emotion Recognition in Conversations
      2026
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MOSI

- [ ] **R0251** · DSSR: Decoupling Salient and Subtle Representations Under Missing Modalities for Multimodal Emotion Recognition
      2026
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MOSEI, MOSI · no results in abstract — check IC4

- [ ] **R0252** · Universal Invariant Framework for Emotion Recognition in Incomplete Multimodality
      2025 · Preprints.org
      [full text](https://www.preprints.org/frontend/manuscript/4244ad7f522946a7eec4aee87d823776/download_pub)

- [ ] **R0253** · A Cross-Modality Graph Attention Network for Robust Multimodal Emotion Recognition with Missing-Modality Handling
      2026 · Zenodo (CERN European Organization for Nuclear
      [full text](https://doi.org/10.5281/zenodo.20842457)
      no results in abstract — check IC4 · **no abstract** — title-only

- [ ] **R0254** · Cascaded Encoder-Decoder Reconstruction Network with Gated Mechanism for Multimodal Emotion Recognition under Missing Modalities
      2024
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MSP-IMPROV

- [ ] **R0255** · Temporal Invariant Feature Combined with Arbitrary Enhancement for Missing Modality Emotion Recognition
      2025
      **no open copy found** — request via library, or contact the author

- [ ] **R0258** · Prompt-Guided Mixture-of-Experts for Robust Multimodal Sentiment Analysis with Missing Modalities
      2026
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MOSEI, MOSI · no results in abstract — check IC4

- [ ] **R0259** · VFFG-CL: Virtual Fusion Feature Generation with Curriculum Learning for Missing-Modality Emotion Recognition
      2025
      **no open copy found** — request via library, or contact the author
      datasets: IEMOCAP, MSP-IMPROV · no results in abstract — check IC4

- [ ] **R0260** · Graph-based Modality Alignment for Robustness in Conversational Emotion Recognition
      2026
      **no open copy found** — request via library, or contact the author
      no results in abstract — check IC4

- [ ] **R0261** · GS³-ICL: Graph-Structured Sparse Selection with Invariance-Consistent Learning for multimodal SER
      2026
      [full text](https://doi.org/10.1145/3805622.3810766)
      datasets: IEMOCAP, MELD, SAVEE · no results in abstract — check IC4


---

## When a paper cannot be read

Record it as excluded under **EC5 (inaccessible)**, not under a content criterion. Access-driven and content-driven exclusions are counted separately in the PRISMA flow, so an unreadable paper stays visible as an access limit rather than disappearing into a relevance judgement. This is threat T7, and it currently affects 24% of the working corpus.
