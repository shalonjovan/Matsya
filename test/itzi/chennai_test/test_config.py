from itzi.configreader import ConfigReader
cfg="chennai.ini"
cr=ConfigReader(cfg)
print("Sim params:", cr.get_sim_params())
print("Grass params:", cr.get_grass_params())
print("Input maps:", cr.get_sim_params().input_map_names)
print("Drainage:", cr.get_sim_params().swmm_inp)
print("Config OK - would run if GRASS available")
# Try to check grass
import shutil
print("grass bin:", shutil.which("grass"))
