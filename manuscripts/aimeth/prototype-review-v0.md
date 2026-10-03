# Independent review of the computational-cell contract prototype

3 October 2026 · Review version 0 · Offline implementation review

Reviewed only `prototypes/cell_contract.py`, `tests/test_cell_contract.py`, and `docs/cell-contract-prototype-v0.md`, with a narrow read of their imported canonical-JSON and identifier helpers. No network, API, credentials, cluster, v8 execution, or source modifications were involved. This document records one substantive defect rather than filling a quota with already declared scope limitations.

**Verdict:** the tested quota, duplicate-rejection, snapshot-hash, and lineage-identity paths behave consistently with the documented bounded, single-writer prototype. Fix the temporal version-provenance defect below before using its accepted histories to validate developmental ordering or a signal-delay intervention. This review does not certify an integrated developmental runtime or scientific capability.

## P2 — A message can predate its sender's birth or the sender state version it claims

Location: `CellContract.apply_signal`, especially the version and lifetime checks at lines 167–171; `CellContract.divide` initializes the daughter at lines 215–223 without a birth/version-established timestamp.

The current checks establish that the sender and receiver versions exist **at delivery**, and that the message creation tick is no later than delivery. They do not establish that the sender, or the sender version asserted by the message, existed **when the message was created**. The parent-message lower bound at lines 180–184 applies only when a parent is supplied. A root message can therefore claim impossible provenance, be committed, consume resource units, and remain accepted after replay.

Observed reproductions on the reviewed source:

| Setup | Accepted message | Result |
|---|---|---|
| Daughter born at tick 10 | Daughter sends a root message with `created_tick=0`, `sender_version=0`, delivered at tick 11 | Accepted; replay also accepts; total units become 3 |
| Seed `b` first changes to version 1 at tick 10 | `b` sends a root message with `created_tick=0`, `sender_version=1`, delivered at tick 11 | Accepted; recipient records the message |

The first example is a direct temporal contradiction, not merely an unspecified policy about stale responses. The second can misattribute a signal to state that did not yet exist. A checksum cannot detect this because the invalid chronology is generated and replayed consistently by the same validator. This matters for the Methods' ancestry, state-version, local development, and response-delay claims: `now - created_tick` can otherwise include time before the sender existed, and apparent signal/state ordering is not causally valid.

Minimal reproduction using the existing test fixtures:

```python
from tests.test_cell_contract import population, signal
from prototypes.cell_contract import CellContract

p = population()
p.divide("birth", parent_id="b", child_id="daughter",
         expected_version=0, parent_state_hash=p.state_hash("b"), now=10)
p.apply_signal("accepted-backdated", signal(
    message_id="predates-birth", sender="daughter", receiver="b",
    sender_version=0, receiver_version=1,
    created_tick=0, expires_tick=20), now=11)
restored = CellContract.from_json(p.to_json())  # Currently succeeds.
assert restored.summary()["units_used"] == 3

q = population()
q.apply_signal("first", signal(expires_tick=20), now=10)
q.apply_signal("backdated-version", signal(
    message_id="m2", sender="b", receiver="c", sender_version=1,
    created_tick=0, expires_tick=20), now=11)  # Currently succeeds.
```

**Concrete fix:** track at least each cell's birth tick and the tick at which its current sender version became valid, reconstructing both deterministically during replay. Reject a message whose creation predates either bound before any mutation or resource charge. Specify whether the receiver-version field identifies a receiver snapshot known at send time or only an expected version at delivery; enforce its temporal lower bound if the former. Likewise, explicitly choose whether an edge must exist at creation or only at delivery, rather than inferring that rule from the current adjacency test. Equal logical ticks still need the recorded event order to distinguish causal ordering when an eventual runtime records message preparation.

Add regression cases for a newly born sender, a newly established sender version, and a valid message created exactly at the allowed boundary. Check that rejection preserves both `to_json()` and observable cell/summary state, and that valid replay preserves the timestamp bookkeeping. The existing parent-before-child-message test should remain in place; it covers a different lower bound.

## Verification and non-findings

Executed:

```sh
python3 -B -m unittest discover -s tests -p 'test_cell_contract.py' -v
```

Observed: **20 test methods passed in 0.009 seconds**. The two additional reproductions above both accepted the impossible chronology; the birth case also survived `from_json` replay. The review inspected rejection order around recording and found no additional demonstrated partial-charge or duplicate-application defect in the supported ordinary-JSON, single-writer paths.

Specifically, duplicate event/message/child identities reject before charging; stale versions and changed division hashes reject; population, synthetic-unit, event, and outgoing-neighbour caps are applied before recording; division inherits detached state; parent-message hashes and parent-delivery chronology are checked; replay compares the reconstructed event including cost and previous hash. These are local code/test observations, not proofs covering every input or concurrency model. Resource requests intentionally do not allocate resources, and the outgoing-only degree bound and current-version delivery policy are stated design choices, not newly discovered defects. The absence of persistence is documented and is not counted as a review finding.

## Reviewed file identities

| File | SHA-256 |
|---|---|
| `prototypes/cell_contract.py` | `ff9574d36f65c2da2b433d66dba25b1655f597993961fab9a714fba55cc8f50d` |
| `tests/test_cell_contract.py` | `564f56af60710da36394954f6271007642986d1597c2bfec21f91b4f640b1f98` |
| `docs/cell-contract-prototype-v0.md` | `7e010bac32ae598aaf49e0ff5cb996766858dd118cf79962108ae4514523d2ac` |

These hashes identify the reviewed versions. A subsequent fix requires rerunning the reproductions and updating the implementation's own validation record; this review should remain as the historical finding.
