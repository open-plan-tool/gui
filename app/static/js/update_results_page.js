$(document).ready(function () {
    const scen_id = "{{ scen_id }}";
    const proj_id = "{{ proj_id }}";
});

function update_kpi_table_style(scen_id="", table_id="summary"){
    $.ajax({
        url: urlRequestKPITable + "?compare_scenario=" + scen_id,
        type: "GET",
        data: {table_id: table_id},
        success: async (table_data) => {
            await addSummaryTable(table_data, table_id);
        }
    });
}

function addSummaryTable(table_data, table_id) {
    let parentDiv = document.getElementById(table_id + "Table");
    parentDiv.innerHTML = "";

    /* create KPI table headers */
    parentDiv.classList.add("table-bordered", "table-hover");
    let tableHead = document.createElement('thead');
    tableHead.classList.add("thead-dark");
    tableHead.style.position = "sticky";
    tableHead.style.top = "0";
    let table_headers = table_data.hdrs; // todo add dynamically more scenarios here
    let table_length = table_headers.length;
    let tableHeadContent = document.createElement('tr');
    table_headers.map(hdr =>
        {
            var tableHdr = document.createElement('th');
            tableHdr.innerHTML = hdr;
            tableHeadContent.appendChild(tableHdr);
        }
    );
    tableHead.appendChild(tableHeadContent);
    parentDiv.appendChild(tableHead);


    for (let subBody in table_data.data) {
        let tableBody = document.createElement('tbody');
        tableBody.id = subBody;
        /* add subtable title */
        const tableSubSectionTitleRow = document.createElement('tr');
        let tableSubSectionTitle = document.createElement('th');
        tableSubSectionTitle.innerHTML = subBody;
        tableSubSectionTitleRow.appendChild(tableSubSectionTitle);
        for(let i=0;i<table_length-1;i += 1){
            tableSubSectionTitleRow.appendChild(document.createElement('td'));
        }

        //tableBody.appendChild(tableSubSectionTitle);

        /* add subtable lines for each parameter */
        // (param should be a json object) with keys name (type str), unit type (str) and scen_values
        /* jshint -W083 */
        table_data.data[subBody].forEach(param =>{
            let tableSubSectionParamRow = document.createElement('tr');
            let cell = tableSubSectionParamRow.insertCell(0);
            cell.innerHTML = param.name + param.description;
            //cell.setAttribute("title", param.description)
            //cell.append(" just to see");
            // todo for loop over scenario values
            for (let i=0;i<param.scen_values.length;i += 1){
                cell = tableSubSectionParamRow.insertCell(1 + i);
                cell.innerHTML = param.scen_values[i] +" " + param.unit;
            }
            tableBody.appendChild(tableSubSectionParamRow);
        });


        parentDiv.appendChild(tableBody);
    }
    $('[data-bs-toggle="tooltip"]').tooltip();

}


function addWideTable(table_data, table_id){
    let parentDiv = document.getElementById(table_id + "Table");
    let titleDiv = document.getElementById(table_id + "TableTitle");
    titleDiv.innerHTML = table_data.title;
    parentDiv.innerHTML = "";

    /* create KPI table headers */
    parentDiv.classList.add("table-bordered", "table-hover");
    let tableHead = document.createElement('thead');
    tableHead.classList.add("thead-dark");
    tableHead.style.position = "sticky";
    tableHead.style.top = "0";
    let table_headers = table_data.hdrs; // todo add dynamically more scenarios here
    let table_length = table_headers.length + 1;
    let tableHeadContent = document.createElement('tr');
    // Add first (empty) header
    tableHeadContent.appendChild(document.createElement('th'));
    table_headers.map(hdr =>
        {
            var tableHdr = document.createElement('th');
            tableHdr.innerHTML = hdr;
            tableHeadContent.appendChild(tableHdr);
        }
    );
    tableHead.appendChild(tableHeadContent);
    parentDiv.appendChild(tableHead);

    // --- build table body ---
    const tableBody = document.createElement('tbody');

    for (const [key, entry] of Object.entries(table_data.data)) {
        const value = {
            verbose: entry.name,
            description: entry.description || "",
            unit: entry.unit || "",
            value: entry.scen_values
        };

        const tableDataRow = document.createElement('tr');

        for (let i = 0; i < table_length; i += 1) {
            const tableDataCell = document.createElement('td');

            let unit = (value.unit === "" ? " " : " (" + value.unit + ") ");

            if (i === 0) {
                // row title
                tableDataCell.innerHTML = value.verbose + unit + value.description;
            } else {
                if (Array.isArray(value.value)) {
                    tableDataCell.innerHTML = value.value[i - 1];
                } else {
                    tableDataCell.innerHTML = value.value;
                }
            }
            // highlight totals
            if (value.verbose.includes("Total")) {
                tableDataCell.style.fontWeight = "bold";
                tableDataCell.style.backgroundColor = "#F9F8F7";
            }

            tableDataRow.appendChild(tableDataCell);
        }

        tableBody.appendChild(tableDataRow);
    }

    // --- append everything ---
    parentDiv.appendChild(tableHead);
    parentDiv.appendChild(tableBody);

    // enable Bootstrap tooltips if any
    $('[data-bs-toggle="tooltip"]').tooltip();
}
/*error: function (xhr, errmsg) {
    console.log("backend_error!")
    //Show the error message
    $('#message-div').html("<div class='alert-error'>" +
        "<strong>Success: </strong> We have encountered an error: " + errmsg + "</div>");
}*/

function request_system_costs_table(scen_id=""){
 $.ajax({
            url: urlRequestSystemCosts + scen_id,
            type: "GET",
            data: {table_id: "system_costs"},
            success: async (table_data) => {
                await addWideTable(table_data, table_id="system_costs");
            },
        });
    }

/* loop over scenario selection buttons and return the ids of the selected ones */
function fetchSelectedScenarios(){
    var selectedScenarios = [];
    var scenariosDropDown = $("#results-scenarios");
    if(scenariosDropDown){
        if(Array.isArray(scenariosDropDown.val()) == false){
            selectedScenarios.push(scenariosDropDown.val().split("-")[2]);
        }
        else{
            selectedScenarios = scenariosDropDown.val();
        }
    }
    return selectedScenarios;
}



function scenario_visualize_timeseries(scen_id=""){
 $.ajax({
            url: urlVisualizeTimeseries + scen_id,
            type: "GET",
            success: async (parameters) => {
                await graph_type_mapping[parameters.type](parameters.id, parameters);
            }
        });
}

function scenario_visualize_stacked_timeseries(scen_id){
 $.ajax({
            url: urlVisualizeStackedTimeseries  + scen_id,
            type: "GET",
            success: async (graphs) => {
                const parentDiv = document.getElementById("stacked_timeseries");
                await graphs.map(parameters => {
                    const newGraph = document.createElement('div');
                    newGraph.id = "stacked_timeseries" + parameters.id;
                    parentDiv.appendChild(newGraph);
                    graph_type_mapping[parameters.type](newGraph.id, parameters);
                });
            },
        });
}


function scenario_visualize_sankey(scen_id, ts=null){
	var urlParams = scen_id;
	if( ts === null || ts === ""){
	}
	else{
		urlParams = scen_id + "/" + ts;
	}
 $.ajax({
            url: urlVisualizeSankey + urlParams,
            type: "GET",
            success: async (parameters) => {
                await graph_type_mapping[parameters.type](parameters.id, parameters);
            },
        });
}

function scenario_visualize_capacities(scen_id=""){
 $.ajax({
            url: urlVisualizeCapacities + scen_id,
            type: "GET",
            success: async (parameters) => {
                await graph_type_mapping[parameters.type](parameters.id, parameters);
            },
        });
}

function scenario_visualize_costs(scen_id=""){
 $.ajax({
            url: urlVisualizeCosts + scen_id,
            type: "GET",
            success: async (graphs) => {
								const parentDiv = document.getElementById("costs");
                await graphs.map(parameters => {
                    const newGraph = document.createElement('div');
                    newGraph.id = "costs" + parameters.id;
                    parentDiv.appendChild(newGraph);
                    if(parameters.title === "var1" || parameters.title === "var2")
            				{ graph_type= parameters.type;
            					parameters.title = "";}
            				else{ graph_type = parameters.type + "Scenarios";}
                    graph_type_mapping[graph_type](newGraph.id, parameters);
                });
            },
        });
}
