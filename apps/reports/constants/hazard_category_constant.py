from dataclasses import dataclass, fields

from apps.reports.definitions import HazardCategoryDefinition


@dataclass(frozen=True)
class AllHazardCategory:
    POTHOLES: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Potholes".title(),
        description=" ".join("""
            Holes, dips, or broken chunks in the road surface. Can look like a bowl-shaped dent, 
            crumbling edges, or chipped/broken concrete at cracks and joints.
        """.split()),
        response_time_days=3
    )

    ALLIGATOR_CRACKS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Alligator Cracks".title(),
        description=" ".join("""
            A web of connected cracks that looks like alligator skin, usually a sign the road surface 
            is breaking down from repeated traffic and wear.
        """.split()),
        response_time_days=3
    )

    MAJOR_SCALING: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Major Scaling".title(),
        description=" ".join("""
            The top layer of a concrete road slab, more than 1cm thick, is flaking or wearing away across 
            the whole slab.
        """.split()),
        response_time_days=30
    )

    SHOVING_AND_CORRUGATION: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Shoving and Corrugation".title(),
        description=" ".join("""
            The road surface has rippled, bulged, or dipped, often from braking or accelerating traffic. 
            Includes wavy washboard bumps, wheel-rut grooves, and low spots in the pavement.
        """.split()),
        response_time_days=10
    )

    PUMPING_AND_DEPRESSION: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Pumping and Depression".title(),
        description=" ".join("""
            Water is being forced out from under the road through cracks, which can make sections rock, 
            shift, or sink, creating dips or uneven steps in the surface.
        """.split()),
        response_time_days=30
    )

    NO_OR_FADED_ROAD_MARKINGS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="No/Faded Road Markings".title(),
        description=" ".join("""
            Lane lines, center lines, edge lines, or crosswalk markings that are missing or too faded to 
            see clearly, meaning less than half is visible.
        """.split()),
        response_time_days=15
    )

    DEFECT_ON_SHOULDERS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Defects on Shoulders".title(),
        description=" ".join("""
            The road shoulder, the strip beside the driving lane, is too low, too high compared to the road, 
            or overgrown with grass or weeds.
        """.split()),
        response_time_days=7
    )

    LUSH_VEGETATION: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Lush Vegetation".title(),
        description=" ".join("""
            Overgrown grass, weeds, shrubs, or tree branches along the roadside that are tall enough to block 
            drivers' view of the road ahead.
        """.split()),
        response_time_days=3
    )

    CLOGGED_DRAINS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Clogged Drains".title(),
        description=" ".join("""
            Drainage channels, ditches, gutters, or culverts blocked by dirt, trash, leaves, or debris, 
            preventing water from draining properly.
        """.split()),
        response_time_days=3
    )

    OPEN_MANHOLE: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Open Manhole".title(),
        description=" ".join("""
            Manhole covers that are missing, broken, uneven, or unsafe, including damaged curb inlets and 
            drainage grates.
        """.split()),
        response_time_days=10
    )

    NO_OR_INADEQUATE_SEALANT_IN_JOINTS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="No/Inadequate Sealant in Joints".title(),
        description=" ".join("""
            The sealant, a protective filler, in pavement joints is missing or insufficient, leaving gaps open.
        """.split()),
        response_time_days=3
    )

    CRACKS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Cracks".title(),
        description=" ".join("""
            General cracking in the road in different shapes and directions, including straight lines, blocks, 
            diagonals, or curved, wandering cracks.
        """.split()),
        response_time_days=3
    )

    RAVELING: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Raveling".title(),
        description=" ".join("""
            The road surface is slowly crumbling apart, losing its small stones and binding material bit by bit.
        """.split()),
        response_time_days=7
    )

    UNMAINTAINED_SIGNAGES_AND_ROAD_MARKERS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Unmaintained Signages and Road Markers".title(),
        description=" ".join("""
            Road signs or markers, such as warning signs, speed signs, or kilometer posts, that are broken, 
            missing, dirty, faded, vandalized, or leaning over.
        """.split()),
        response_time_days=15
    )

    UNMAINTAINED_BRIDGES: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Unmaintained Bridges".title(),
        description=" ".join("""
            Problems on bridges, such as a dirty or damaged bridge deck, broken curbs, sidewalks or railings, 
            or faded and unpainted bridge parts and name signs.
        """.split()),
        response_time_days=15
    )

    UNMAINTAINED_GUARDRAILS: HazardCategoryDefinition = HazardCategoryDefinition(
        hazard_name="Unmaintained Guardrails".title(),
        description=" ".join("""
            Guardrails that are damaged, dirty, vandalized, missing, unpainted, misaligned, or leaning.
        """.split()),
        response_time_days=15
    )

    @classmethod
    def get_flat_list(cls) -> list[HazardCategoryDefinition]:
        categories = []

        for category in fields(cls):
            categories.append(category.default)

        return categories