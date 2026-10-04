# AIMeth primary-literature positioning — v0

Verified: 2026-10-03. Scope: a targeted primary-source positioning review, not a systematic review or proof of novelty. Sources were checked against publisher/proceedings pages, author-deposited papers or versioned arXiv records. Findings below are source-reported; AIMeth interpretations and proposed tests are explicitly separated. No AIMeth emergence result is established by these citations.

## Verified reference and claim ledger

### R1 — Learned local rules can produce and repair target morphology

**Alexander Mordvintsev, Ettore Randazzo, Eyvind Niklasson and Michael Levin (2020). “Growing Neural Cellular Automata.” Distill.** DOI: [10.23915/distill.00023](https://doi.org/10.23915/distill.00023). [Primary full text](https://distill.pub/2020/growing-ca/).

- **Supported finding:** A shared learned local update rule produces target images from seed states. Training on persistent states and damage can improve maintenance and regeneration. Cell states differ while the update rule is shared.
- **Does not establish:** Unsupervised discovery of the target morphology, autonomous biological reproduction, broad problem-solving intelligence or superiority of larger Agent populations. Target images and global training losses are supplied.
- **AIMeth implication:** Separate shared module parameters from cell-specific activation/state; record which geometry was prescribed. Treat growth, persistence and regeneration as distinct outcomes.
- **Verification scope:** Full text, Model and Experiments 1–3; bibliographic record checked.

### R2 — Local communication can support a global classification task

**Ettore Randazzo, Alexander Mordvintsev, Eyvind Niklasson, Michael Levin and Sam Greydanus (2020). “Self-classifying MNIST Digits.” Distill.** DOI: [10.23915/distill.00027.002](https://doi.org/10.23915/distill.00027.002). [Primary full text](https://distill.pub/2020/selforg/mnist/).

- **Supported finding:** A neural cellular automaton uses local message passing so cells occupying a handwritten digit classify its global identity and can update their classification when the underlying digit changes.
- **Does not establish:** Discovery of the input shape, superiority over optimized conventional classifiers, or mathematically verified reasoning. The digit's occupied pixels are supplied; disconnected components create a stated limitation.
- **AIMeth implication:** A communication-restricted collective computation baseline is already available in the literature. Morphology recognition and morphology creation must not be conflated.
- **Verification scope:** Full text, task definition and Model, including immutable pixel channel and connectivity caveat.

### R3 — Morphological self-organization already exists in physical swarms

**Ivica Slavkov, Daniel Carrillo-Zapata, Noemí Carranza, X. Diego, Fredrik Jansson, Jaap A. Kaandorp, Sabine Hauert and James Sharpe (2018). “Morphogenesis in robot swarms.” Science Robotics 3, eaau9178.** DOI: [10.1126/scirobotics.aau9178](https://doi.org/10.1126/scirobotics.aau9178). [Author institution record and manuscript link](https://research-information.bris.ac.uk/en/publications/morphogenesis-in-robot-swarms/).

- **Supported finding:** Local neighbor interactions enable 300 physical robots to form adaptable shapes without self-localization; damage robustness is reported.
- **Does not establish:** Task-driven Agent proliferation, a learned artificial genome, general intelligence, or a computational advantage on held-out reasoning tasks.
- **AIMeth implication:** Self-organized geometry alone is insufficient novelty. Functional consequences must be measured independently of shape resemblance.
- **Verification scope:** Author institution abstract and bibliographic record; publisher full text was not accessible in this pass. X. Diego is retained as an initial because repository and search-rendered given names differ.

### R4 — Communication can organize multiple dynamical scales

**Alexander Ziepke, Ivan Maryshev, Igor S. Aranson and Erwin Frey (2022). “Multi-scale organization in communicating active matter.” Nature Communications 13, 6727.** DOI: [10.1038/s41467-022-34484-2](https://doi.org/10.1038/s41467-022-34484-2). [Primary article](https://www.nature.com/articles/s41467-022-34484-2).

- **Supported finding:** In a model of signaling self-propelled agents, local processing and communication support successive collective states, including droplets, streams and vortices. Signal susceptibility affects aggregation dynamics.
- **Does not establish:** Semantic reasoning, arbitrary-task intelligence or universal population thresholds for tissue formation.
- **AIMeth implication:** Track intermediate structures and temporal transitions, not just final connectivity. Perturb signals to test whether the developmental trajectory changes.
- **Verification scope:** Publisher-indexed full-text sections on aggregation, cluster analysis and citation metadata. The publisher gives article number **6727**; an author-lab webpage lists 6726, which is not used here.

### R5 — Decentralized cellular computation reaches physical hardware

**Rodrigo Moreno, Andrés Faiña, Shyam Sudhakaran, Kathryn Walker and Sebastian Risi. “Smart Cellular Bricks for Decentralized Shape Classification and Damage Recovery.”** [Author-deposited primary paper, arXiv:2509.18659 (2025)](https://arxiv.org/abs/2509.18659). The journal article appeared in **Nature Communications (2026)** as [“Smart cellular bricks for decentralized shape classification and damage recovery,” DOI:10.1038/s41467-026-75166-7](https://www.nature.com/articles/s41467-026-75166-7).

- **Supported finding:** Identical local NCA controllers allow physical 3D modules to classify assembled shapes. The journal article separately reports simulated damage localization and recovery.
- **Does not establish:** Physical autonomous growth or repair of the hardware, superior general reasoning, or a requirement for natural-language messages. Simulated recovery must not be described as physical regeneration.
- **AIMeth implication:** Compact local states can support useful collective computation; latency, fault tolerance and task accuracy need separate measurements.
- **Verification scope:** arXiv author record; publisher-indexed Methods, Discussion and simulated recovery sections. No exact hardware accuracy claim is imported.

### R6 — Learned communication does not require natural language

**Jakob N. Foerster, Yannis M. Assael, Nando de Freitas and Shimon Whiteson (2016). “Learning to Communicate with Deep Multi-Agent Reinforcement Learning.” Advances in Neural Information Processing Systems 29.** [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2016/hash/c7635bfd99248a2cdef8249ef7bfbef4-Abstract.html); [versioned author paper](https://arxiv.org/abs/1605.06676v2), DOI:10.48550/arXiv.1605.06676.

- **Supported finding:** RIAL and DIAL learn task-dependent communication in partially observed cooperative environments. DIAL uses gradient information through communication channels during centralized training and decentralized execution.
- **Does not establish:** Fully local learning, cell proliferation, spatial tissue development or LLM-scale reasoning.
- **AIMeth implication:** Separate training information access from deployment communication constraints; include vector/symbolic signals as legitimate alternatives to language.
- **Verification scope:** Proceedings abstract and paper title page. Proceedings metadata expands Assael's name differently; the author-paper form is used above.

### R7 — Optimizing Agent operations and connections is prior art

**Mingchen Zhuge, Wenyi Wang, Louis Kirsch, Francesco Faccio, Dmitrii Khizbullin and Jürgen Schmidhuber (2024). “GPTSwarm: Language Agents as Optimizable Graphs.” Proceedings of the 41st International Conference on Machine Learning, PMLR 235, 62743–62767.** [Primary proceedings paper](https://proceedings.mlr.press/v235/zhuge24a.html).

- **Supported finding:** The framework represents language-agent operations as graph nodes, information flow as edges, and optimizes prompts and inter-agent connections.
- **Does not establish:** Local cell division, developmental lineage, tissue morphogenesis or a universal benefit from increasing population size.
- **AIMeth implication:** Renaming prompts “genes” and graphs “tissues” adds no demonstrated mechanism. The proposed developmental operations need explicit interventions and advantages beyond graph optimization.
- **Verification scope:** Proceedings abstract and bibliographic record. The arXiv title omits “GPTSwarm”; the published title is used.

### R8 — Task-conditioned communication topology is also prior art

**Guibin Zhang, Yanwei Yue, Xiangguo Sun, Guancheng Wan, Miao Yu, Junfeng Fang, Kun Wang, Tianlong Chen and Dawei Cheng (2025). “G-Designer: Architecting Multi-agent Communication Topologies via Graph Neural Networks.” Proceedings of the 42nd International Conference on Machine Learning, PMLR 267, 76678–76692.** [Primary proceedings paper](https://proceedings.mlr.press/v267/zhang25cu.html).

- **Supported finding:** A graph-based learned designer produces task-adaptive communication topologies; the authors evaluate task performance, communication cost and adversarial robustness.
- **Does not establish:** That task-aware edge adaptation is developmental self-organization, that changes arise from local rules, or that its benchmark gains generalize to 10K populations.
- **AIMeth implication:** Include a task-conditioned topology baseline. Otherwise any advantage could be ordinary routing optimization rather than differentiation or proliferation.
- **Verification scope:** Proceedings abstract and bibliographic record; headline numerical gains are not imported without auditing their comparison denominators.

### R9 — More coordination is not uniformly better

**Yubin Kim, Ken Gu, Chanwoo Park, Chunjong Park, Samuel Schmidgall, A. Ali Heydari, Yao Yan, Zhihan Zhang, Yuchen Zhuang, Yun Liu, Mark Malhotra, Paul Pu Liang, Hae Won Park, Yuzhe Yang, Xuhai Xu, Yilun Du, Shwetak Patel, Tim Althoff, Daniel McDuff and Xin Liu (2025; revised 2026). “Towards a Science of Scaling Agent Systems.”** [arXiv:2512.08296v3, 8 April 2026](https://arxiv.org/abs/2512.08296v3); DOI:10.48550/arXiv.2512.08296. **Preprint.**

- **Supported finding:** The version-3 abstract reports controlled comparisons across 260 configurations and six benchmarks, with architecture-dependent gains and losses, coordination overhead and capability saturation.
- **Does not establish:** A universal scaling law, a threshold beyond which all collectives fail, or outcomes for AIMeth's proposed developmental architecture.
- **AIMeth implication:** Compare total-cost-matched architectures, preserve negative outcomes and condition conclusions on task structure.
- **Verification scope:** Current author record and version-3 abstract. Search snippets still report the earlier 180-configuration/four-benchmark version; those figures are not used.

## Draft Introduction and novelty argument

*Proposed manuscript prose; not a statement of completed AIMeth findings. Approximately 500 words.*

Increasing the number of computational agents expands available computation, but does not specify how that computation becomes coordinated or useful. A developmental approach asks a different question: can a population construct and revise its own organization in response to a task, and does that process improve what the population can accomplish? This question requires separating the formation of structure from the acquisition of function. A visually coherent arrangement, stable consensus or large message volume is not by itself evidence of improved problem solving.

Several research traditions make this distinction experimentally accessible. Neural cellular automata learn shared local rules that grow and repair prescribed patterns, while related models use neighboring cell states to classify a global digit. These studies establish useful mechanisms for distributed state updating, but their task inputs and training objectives remain externally specified. Physical robot swarms and models of communicating active matter further show that local interactions can organize collective morphology across spatial scales. Recent cellular-brick systems extend decentralized classification to three-dimensional hardware, while their recovery demonstrations must be distinguished from physical self-repair. Together, these findings motivate computational development without establishing that morphogenesis generally produces intelligence. [R1](https://distill.pub/2020/growing-ca/), [R2](https://distill.pub/2020/selforg/mnist/), [R3](https://research-information.bris.ac.uk/en/publications/morphogenesis-in-robot-swarms/), [R4](https://www.nature.com/articles/s41467-022-34484-2), [R5](https://www.nature.com/articles/s41467-026-75166-7).

Communication itself is also a learnable component rather than necessarily a natural-language dialogue. Differentiable inter-agent learning demonstrated that cooperative policies can acquire communication protocols under partial observation, while distinguishing centralized training from decentralized execution. In language-agent systems, GPTSwarm optimizes computational operations and their connections, and G-Designer learns task-conditioned communication topologies. Consequently, neither adaptive connectivity nor biological terminology alone would constitute a distinct contribution. A recent controlled comparison of agent architectures additionally reports both benefits and substantial degradations across tasks, arguing against an unconditional “more agents is better” premise. [R6](https://arxiv.org/abs/1605.06676v2), [R7](https://proceedings.mlr.press/v235/zhuge24a.html), [R8](https://proceedings.mlr.press/v267/zhang25cu.html), [R9](https://arxiv.org/abs/2512.08296v3).

AIMeth therefore proposes an intervention-based test of developmental organization. A computational cell is defined by persistent local state, bounded computation and an explicit communication interface. Candidate artificial genes are reusable, independently perturbable functional modules; expression denotes their state-dependent activation. These operational definitions are engineering hypotheses, not claims that model weights reproduce biological genetics. Differentiation changes a cell's functional activation pattern, whereas proliferation creates a traceable descendant and incurs additional resource cost. Mesoscopic organization is measured from interaction and state dynamics rather than assigned solely from a drawing of the network.

The decisive test is whether task-conditioned development improves independently measured performance after accounting for model capacity, training, inference, communication and elapsed time. Independently initialized populations provide replication. Fixed organizations, task-adaptive graph designs and interventions that disrupt signaling or proliferation provide competing explanations and controls. Mathematics supplies one demanding evaluation domain in which claimed results can undergo proof checking; it does not define intelligence or remove the need for empirical comparisons of computational systems. The intended contribution is thus a causal account of when developmental organization helps, when it fails and what it costs. Establishing that contribution remains contingent on experiments; the present evidence does not yet support an emergence claim.

## Immediate implications for the manuscript and experiments

1. **Defensible novelty candidate:** A measured developmental sequence linking local regulation, differentiation/proliferation, mesoscopic organization and a task benefit that survives matched-cost and disrupted-organization controls. This is a proposed contribution, not a priority claim or completed result.
2. **Required alternative explanations:** Extra sampling, larger effective memory, greater total computation, centralized training information, optimized routing, evaluator leakage and population-dependent communication overhead.
3. **Minimum interpretation discipline:** Report imposed structures separately from locally generated structures; treat modules as genes only operationally; report latency and task benefit separately; do not infer biological causation from expression maps alone.

The pepper spatial-transcriptomics article motivating the project is not identified in this review. Its exact bibliographic identity and source claims must be recovered from the project's supplied primary material before citation. No title, gene mechanism or metabolite-production result has been inferred from the user's description.
