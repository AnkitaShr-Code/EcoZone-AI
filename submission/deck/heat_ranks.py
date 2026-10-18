import sys, json
sys.path.insert(0, "evals")
from evalkit import heat_check as hc
from evalkit.bundle import describe, choose_bundle
import ecozone_engine as e
info = describe(choose_bundle())
print("bundle", info.path)
area = e.load_bundle(info.path)
baselines = dict(area.block_baselines)
lst = hc.read_lst(hc.csv_path(info.area_id))
frame = hc.join_blocks(lst, baselines, info.split)
for k, c in hc.correlations(frame, "hei").items():
    print(k, c.n, round(c.rho, 3), round(c.p_value, 4))
# ranks within all blocks (1 = coolest / lowest)
frame["hei_rank"] = hc.average_ranks(frame["hei"].to_numpy())
frame["lst_rank"] = hc.average_ranks(frame["lst"].to_numpy())
out = [{"b": r.block_id, "s": r.split, "h": float(r.hei_rank), "l": float(r.lst_rank)} for r in frame.itertuples()]
json.dump(out, open("deck-work/heat_ranks.json", "w"))
print(len(out))
