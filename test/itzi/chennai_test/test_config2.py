from itzi.configreader import ConfigReader
import pathlib
cfg=pathlib.Path(__file__).parent / "chennai.ini"
cr=ConfigReader(str(cfg))
print("OK", cfg)
print(cr.get_sim_params())
print("GRASS", cr.get_grass_params())
