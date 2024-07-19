from scripts.helpers.utility import jopen, load_def_multiple, load_save, retrieve_from_tree
compat_dict = jopen("./scripts/checkers/compat_dict.json")


def resolve_compatibility(variable, version):
    compat_key = compat_dict[variable]
    if version in compat_key:
        return compat_key[version]
    elif (v2 := ".".join(version.split(".")[:-1])) in compat_key:
        return compat_key[v2]
    else:
        while True:
            v2 = v2.split(".")
            v2[-1] = str(int(v2[-1]) - 1)
            if int(v2[-1]) < 1:
                raise ValueError("Compatibility resolve failed")
            v2 = ".".join(v2)
            if v2 in compat_key:
                return compat_key[v2]


def resolve_compatibility_multiple(variables, version):
    out_variables = {variable:resolve_compatibility(variable, version) for variable in variables}
    print(version)
    print(out_variables)
    return out_variables


def companies_manager(save_data, countries, relevant_modifiers):
    """
    Provides checkers with information of companies with relevant traits
    """
    def_companies = dict()
    companies = load_def_multiple("company_types", "Common Directory")
    for name, company_name in companies.items():
        if any([x in relevant_modifiers for x in company_name["prosperity_modifier"]]):
            def_companies.update({name:company_name["prosperity_modifier"]})

    companies = save_data["companies"]["database"]
    for name, company_name in companies.items():
        if "prosperity" not in company_name or not float(company_name["prosperity"]) >= 100:
            continue
        country = company_name["country"]
        if retrieve_from_tree(countries, [country, "definition"]) is None:
            continue
        if (company := retrieve_from_tree(def_companies, [company_name["company_type"]])) is None:
            continue
        if "companies" not in countries[country]:
            countries[country]["companies"] = dict()
        countries[country]["companies"][company_name["company_type"]] = company


def get_country_name(country:dict, localization:dict):
    country_tag = country["definition"]
    if country_tag in localization:
        country_name = localization[country_tag]
    else:
        country_name = country_tag
    if retrieve_from_tree(country, "civil_war") is not None:
        country_name = "Revolutionary " + country_name
    return country_name


def get_version(address):
    meta_data = load_save(["meta_data"], address)["meta_data"]
    version = meta_data["version"]
    return version


def get_building_output(building, target, def_production_methods):
    """
    Calculate a building's output of a variable with respected to production methods, employees and throughput
    Employees must be added into a building from the outside in building["pops_employed"]
    """
    output = 0
    employees = 0
    employees_pl = dict()
    for pm_name in building["production_methods"]["value"]:
        pm = def_production_methods[pm_name]
        if (output_workforce := retrieve_from_tree(pm, ["country_modifiers", "workforce_scaled", target])) is not None:
            output += float(output_workforce)
        if (employees_dict := retrieve_from_tree(pm, ["building_modifiers", "level_scaled"])) is not None:
            for key, addition in employees_dict.items():
                if key not in employees_pl:
                    employees_pl[key] = int(addition)
                else:
                    employees_pl[key] += int(addition)

    if "pops_employed" in building:
        for key, pop in building["pops_employed"].items():
            employees += int(pop["workforce"] )

    # print(employees_pl)
    # print(f"Total Employees at level {int(building['level'])}: {employees}")
    employees /= sum([employees_pl[e] for e in employees_pl])
    # print(f"Employees ratio: {employees}")
    # print([employees_pl[e] for e in employees_pl])
    if "throughput" not in building:
        building["throughput"] = 1.0
    # print(output)
    output =  output * float(building["throughput"]) * employees
    return output