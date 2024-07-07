# This file is updated using the following command

# (echo -n "HEATPUMP_MODELS =" ;curl -f -s https://raw.githubusercontent.com/Egyras/HeishaMon/master/HeatPumpType.md | grep "WH-" | ruby -r json -e 'puts(STDIN.read.split("\n").map { |line|
#   _, id, bytes, idu, odu, kit, power, phase_count, tcap = line.split("|").map(&:strip);
#   model = [idu, odu, kit].reject {|el| el == "Monoblock" }.first;
#   [id, "#{model} #{power} #{phase_count} #{tcap}"]
# }.to_h.to_json)') >> models.py

HEATPUMP_MODELS = {
    "0": "WH-MDC05H3E5 5 1ph HP",
    "1": "WH-MDC07H3E5 7 1ph HP",
    "2": "WH-SXC09H3E5 9 1ph T-CAP",
    "3": "WH-SDC09H3E8 9 3ph HP",
    "4": "WH-SXC09H3E8 9 3ph T-CAP",
    "5": "WH-SXC12H9E8 12 3ph T-CAP",
    "6": "WH-SXC16H9E8 16 3ph T-CAP",
    "7": "WH-SDC05H3E5 5 1ph HP",
    "8": "WH-SDC0709J3E5 9 1ph HP",
    "9": "WH-MDC05J3E5 5 1ph HP",
    "10": "WH-MDC09H3E5 9 1ph HP",
    "11": "WH-MXC09H3E5 9 1ph T-CAP",
    "12": "WH-ADC0309J3E5 9 1ph HP - All-In-One",
    "13": "WH-ADC0916H9E8 12 3ph T-CAP - All-In-One",
    "14": "WH-SQC09H3E8 9 3ph T-CAP - Super Quiet",
    "15": "WH-SDC09H3E5 9 1 ph HP",
    "16": "WH-ADC0309H3E5 9 1 ph HP - All-In-One",
    "17": "WH-ADC0309J3E5 5 1ph HP - All-In-One",
    "18": "WH-SDC0709J3E5 7 1 ph HP",
    "19": "WH-SDC07H3E5-1 7 1 ph HP",
    "20": "WH-MDC07J3E5 7 1ph HP",
    "21": "WH-MDC09J3E5 9 1ph HP",
    "22": "WH-SDC0305J3E5 5 1ph HP",
    "23": "WH-MXC09J3E8 9 3ph T-CAP",
    "24": "WH-MXC12J9E8 12 3ph T-CAP",
    "25": "WH-ADC1216H6E5 12 1ph T-CAP",
    "26": "WH-ADC0309J3E5C 7 1ph HP - All-In-One Compact",
    "27": "WH-MDC07J3E5 7 1ph HP (new version?)",
    "28": "WH-MDC05J3E5 5 1ph HP (new version)",
    "29": "WH-UQ12HE8 12 3ph T-CAP - Super Quiet",
    "30": "WH-SXC12H6E5 12 1ph T-CAP",
    "31": "WH-MDC09J3E5 9 1ph HP (new version?)",
    "32": "WH-MXC09J3E5 9 1ph T-CAP",
    "33": "WH-ADC1216H6E5C 12 1ph HP - All-In-One Compact",
    "34": "WH-ADC0509L3E5 7 1ph HP - All-In-One L-series",
    "35": "WH-SXC09H3E8 9 3ph T-CAP - new version",
    "36": "WH-ADC0309K3E5AN 7 1ph HP - All-In-One K-series - AN",
    "37": "WH-SDC0309K3E5 5 1ph HP - split K-series",
    "38": "WH-SDC0309K3E5 7 1ph HP - split K-series",
    "39": "WH-ADC0916H9E8 16 3ph T-CAP - All-In-One",
    "40": "WH-ADC0912H9E8 12 3ph T-CAP - All-In-One",
    "41": "WH-SDC12H9E8 12 3ph HP",
    "42": "WH-MXC16J9E8 16 3ph T-CAP",
}
