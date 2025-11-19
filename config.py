from dataclasses import dataclass

@dataclass
class EmiliaTunnelConfig:
    """
    Emilia Tunnel Config
    Real experiment:
    https://www.mdpi.com/2075-5309/14/11/3654
    https://kongresdrogowy.pl/wp-content/uploads/2024/05/2.GDDKiA-Prezentacja-Pozar-02-02-2024.pdf
    """

    # --- Tunnel geometry (Laliki) ---
    length_m: float = 678.0     # tunnel len
    lane_width_m: float = 3.5
    num_lanes: int = 2
    shoulder_width_m: float = 0.7
    side_width_m: float = 1.2
    # Approximate usable width (2 lanes + aprons + sidewalks)
    width_m: float = 10.0

    cross_passage_spacing_m: float = 170.0
    num_cross_passages: int = 4

    # --- 2D smoke mesh ---
    dx_m: float = 2.0   # mesh opening along the tunnel
    dy_m: float = 1.0   # mesh opening across the tunnel

    # --- ventilation / air flow ---
    default_air_velocity_x_mps: float = 2.0
    default_air_velocity_y_mps: float = 0.0
    max_air_velocity_mps: float = 10.0

    # --- smoke model ---
    smoke_diffusivity: float = 0.05     # (m^2/s) - simplified
    smoke_decay: float = 0.001     # smoke extraction
    # K = extinction_per_density * density  [1/m]
    extinction_per_density: float = 1.0
    # Visibility ~ visibility_coefficient_m / K  (Jin / SFPE)
    visibility_coefficient_m: float = 3.0

    # --- pedestrians / social force ---
    pedestrian_radius_m: float = 0.25
    pedestrian_mass_kg: float = 80.0
    pedestrian_desired_speed_clear: float = 1.3  # m/s in clear air
    relaxation_time_s: float = 0.5  # time to reach the target speed

    # Social forces parameters (Helbing & Molnár)
    sf_A_social: float = 2.0  # N – The power to repel other people
    sf_B_social: float = 0.8  # m – The range of the force
    sf_A_wall: float = 4.0  # N – Pushing away from walls / obstacles
    sf_B_wall: float = 0.4  # m

    neighbor_radius_m: float = 3.0  # Range of neighborly interactions / herding

    # --- social behavior ---
    # herding – increases when visibility decreases
    herding_max_weight: float = 0.8
    herding_visibility_threshold_m: float = 15.0

    # walking along the wall in the smoke
    wall_follow_visibility_threshold_m: float = 10.0
    wall_follow_max_weight: float = 0.7

    # --- walking speed vs visibility ---
    # Based of the recommendations of Fridolf/Ronchi (Jin + other research review)
    vis_full_speed_threshold_m: float = 3.0  # above 3 m people walk ~normally
    vis_min_speed_mps: float = 0.2  # „complete darkness” / thick smoke
    vis_slowing_slope: float = 0.34  # [m/s per meter of visibility] for the base 1 m/s

    # --- physiology / toxicity of smoke (FED) ---
    # Instead of a full mixture of CO, HCN, etc., we use simplified FED ~smoke density
    # Full Purser model / ISO 13571
    fed_smoke_coeff_per_s: float = 0.002  # how many FED/s for density=1
    fed_incapacitated_threshold: float = 1.0  # FED>=1 => unable to move

    # --- delay in people's reaction's ---
    reaction_time_min: float = 5.0  # s
    reaction_time_max: float = 60.0  # s

    # --- simulation time step ---
    dt_s: float = 0.1

    # --- smoke extraction fans ---
    fan_default_radius_m: float = 10.0
    # smoke removal rate [1/s] in the center of fan
    fan_default_removal_coeff_per_s: float = 0.3
    fan_max_removal_coeff_per_s: float = 1.0

    # "suction" speed into the fan [m/s] (at the edge - realistically something in the order of 1-5 m/s)
    fan_default_flow_mps: float = 3.0


DEFAULT_CONFIG = EmiliaTunnelConfig()


