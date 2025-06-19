// Constants
const ASSET_TYPE_NAME = 'asset_type_name';
const BUS = "bus";
// UUID to Drawflow Id Mapping
// const nodeToDbId = { 'bus': [], 'asset': [] };
const nodesToDB = new Map();
var guiModalDOM = document.getElementById("guiModal");
var guiModal = new bootstrap.Modal(guiModalDOM);

var copCollapseDOM = document.getElementById('form-computeCOP');
if(copCollapseDOM){
    var copCollapse = new bootstrap.Collapse(copCollapseDOM);
    // refresh the field of the projects/forms.py::COPCalculatorForm to plot the data if any
    copCollapseDOM.addEventListener('shown.bs.collapse', function () {
        tHighDOM = guiModalDOM.querySelector('input[name="temperature_high_scalar"]');
        if(tHighDOM){tHighDOM.dispatchEvent(new Event('change'));}
        tLowDOM = guiModalDOM.querySelector('input[name="temperature_low_scalar"]');
        if(tLowDOM){tLowDOM.dispatchEvent(new Event('change'));}
    });
}



// Initialize Drawflow
const id = document.getElementById("drawflow");
const editor = new Drawflow(id);
editor.reroute = true;
editor.start();
// editor.drawflow.drawflow.Home.data; // All node level data are saved here

/* Mouse and Touch Actions */
var elements = document.getElementsByClassName('drag-drawflow');
for (let i = 0; i < elements.length; i++) {
    elements[i].addEventListener('touchend', drop, false);
    elements[i].addEventListener('touchstart', drag, false);
}
var elements = document.getElementsByClassName('section__component');
for (let i = 0; i < elements.length; i++) {
    elements[i].addEventListener('touchend', drop, false);
    elements[i].addEventListener('touchstart', drag, false);
}
function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    // corresponds to data-node defined in templates/scenario/topology_drag_items.html
    ev.dataTransfer.setData("node", ev.target.getAttribute('data-node'));
}

function drop(ev) {
    ev.preventDefault();
    // corresponds to data-node defined in templates/scenario/topology_drag_items.html
    const nodeName = ev.dataTransfer.getData("node");
    addNodeToDrawFlow(nodeName, ev.clientX, ev.clientY);
}


// Disallow Any Connection to be created without a bus.
editor.on('connectionCreated', function (connection) {
    var nodeIn = editor.getNodeFromId(connection.input_id);
    var nodeOut = editor.getNodeFromId(connection.output_id);
    if ((nodeIn.name !== BUS && nodeOut.name !== BUS) || (nodeIn.name === BUS && nodeOut.name === BUS)) {
        editor.removeSingleConnection(connection.output_id, connection.input_id, connection.output_class, connection.input_class);
        Swal.fire('Unexpected Connection', 'Please connect assets to each other\n only through a bus node. Interconnecting busses is also not allowed.', 'error');
    }
});

// might be redundant
editor.on('nodeCreated', function (nodeID) {
    // region bind installed_capacity to age_installed Changes
    // const nodeIdInstalledCapInput = document.getElementById(`node-${nodeID}`).querySelector("input[name='installed_capacity']");
    // if (nodeIdInstalledCapInput) {
    //     nodeIdInstalledCapInput.addEventListener('change', function (e) {
    //         const ageInstalledElement = e.target.closest("#FormGroup").querySelector("input[name='age_installed']");
    //         if (e.target.value === '0') {
    //             ageInstalledElement.value = '0';
    //             ageInstalledElement.readOnly = true;
    //             let notifyAgeInputEvent = new Event("input", { bubbles: true });
    //             ageInstalledElement.dispatchEvent(notifyAgeInputEvent);
    //         } else
    //             ageInstalledElement.readOnly = false;
    //     });
    //     // for existing nodes check if installed cap is zero and set age_installed to read only
    //     if (nodeIdInstalledCapInput.value === '0')
    //         nodeIdInstalledCapInput.closest("#FormGroup").querySelector("input[name='age_installed']").readOnly = true;
    // }
    // endregion
});

editor.on('nodeRemoved', function (nodeID) {
    // remove nodeID from nodesToDB
    nodesToDB.delete('node-'+nodeID);
});


async function addNodeToDrawFlow(name, pos_x, pos_y, nodeInputs = 1, nodeOutputs = 1, nodeData = {}) {
    if (editor.editor_mode === 'fixed')
        return false;
    pos_x = pos_x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)) - (editor.precanvas.getBoundingClientRect().x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)));
    pos_y = pos_y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)) - (editor.precanvas.getBoundingClientRect().y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)));
    return createNodeObject(name, nodeInputs, nodeOutputs, nodeData, pos_x, pos_y);
}

// TODO potentially remove this function
function updateInputTimeseries(){
    //connected to the templates/asset/asset_create_form.html content
    /*ts_data_div = document.getElementById("input_timeseries_data");
    if(ts_data_div){
        var ts_data = JSON.parse(ts_data_div.querySelector("textarea").value);
        var ts_data = ts_data.map(String);
        var ts_idx = [...Array(ts_data.length).keys()];
        ts_idx = ts_idx.map(String);
        makePlotly( ts_idx, ts_data, plot_id="timeseries_trace")
    }*/
}

// find out the name of the other nodes the given node is connected to
function getInputOutputMapping(nodeId){
    var input_output_mapping = {"inputs": {}, "outputs": {}};
    editor.getNodeFromId(nodeId).inputs.input_1.connections.map(c => {const nodeIn = editor.getNodeFromId(parseInt(c.node)); input_output_mapping.inputs[nodeIn.data.bustype] = nodeIn.data.name;});
    editor.getNodeFromId(nodeId).outputs.output_1.connections.map(c => {const nodeOut = editor.getNodeFromId(parseInt(c.node)); input_output_mapping.outputs[nodeOut.data.bustype] = nodeOut.data.name;});
    input_output_mapping.inputs = JSON.stringify(input_output_mapping.inputs);
    input_output_mapping.outputs = JSON.stringify(input_output_mapping.outputs);

    return input_output_mapping;
}

// COP calculation from temperature
function toggle_cop_modal(event){

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'

    let getUrl = copGetUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        getUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    fetch(getUrl).then(response => response.text()).then(formContent => {
        // assign the content of the form to the form tag of the modal
        guiModalDOM.querySelector('form .modal-addendum').innerHTML = formContent;
        // Manually re-initialize tooltips
        document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            if (!bootstrap.Tooltip.getInstance(el)) {
                new bootstrap.Tooltip(el);
            }
        });
    }).catch(error => {
        console.error(error);
    });
}

// function to compute the COP of a heat pump linked with the button of id="btn-computeCOP" in templates/scenario//scenario_step2.html
function computeCOP(event){

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'
    const copForm = event.target.closest('.modal-content').querySelector('#copForm');
    const formData = new FormData(copForm);

  // copPostUrl is defined in scenario_step2.html
    let postUrl = copPostUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        postUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    // send the form of the asset to be saved in database (projects/views.py::asset_cops_create_or_update)
    fetch(postUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
        body: formData,
    }).then(response => response.json()).then(jsonRes => {
        if (jsonRes.success) {
            console.log(jsonRes.cops);
            console.log(jsonRes.cop_id);
            // close the cop area
            copCollapse.hide();

            efficiencyDOM = guiModalDOM.querySelector('input[name="efficiency_scalar"]');
            if(efficiencyDOM){
                efficiencyDOM.value = jsonRes.cops;
                efficiencyDOM.dispatchEvent(new Event('change'));
            }
            copDOM = guiModalDOM.querySelector('input[name="copId"]');
            if(copDOM){
                copDOM.value = jsonRes.cop_id;
            }
        } else {
            // not success: assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('form .modal-addendum').innerHTML = jsonRes.form_html;
        }
    }).catch(error => {
        console.error(error);
        alert(error.message);
    });
}


// one needs to add this function as event with eventListener (<some jquery div>.addEventListener("dblclick", dblClick))
function dblClick(e) {

    const closestNode = e.target.closest('.drawflow-node');

    if (closestNode) {
        const nodeType = closestNode.querySelector('.box').getAttribute(ASSET_TYPE_NAME);
        const topologyNodeId = closestNode.id;

        const nodeId = parseInt(topologyNodeId.split("-").pop());
        const input_output_mapping = getInputOutputMapping(nodeId);
        // formGetUrl is defined in scenario_step2.html
        let getUrl = formGetUrl + nodeType;
        if (nodesToDB.has(topologyNodeId))
            getUrl += "/" + nodesToDB.get(topologyNodeId).uid;
        // add input_output_mapping as GET parameters
        getUrl += '?' + new URLSearchParams(input_output_mapping);

        // get the form of the asset of the type "nodeType" (projects/views.py::get_asset_create_form)
        fetch(getUrl).then(response => response.text()).then(formContent => {
            // assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('form .modal-body').innerHTML = formContent;

            // set parameters which uniquely identify the asset
            guiModalDOM.setAttribute("data-node-type", nodeType);
            guiModalDOM.setAttribute("data-node-topo-id", topologyNodeId);
            guiModalDOM.setAttribute("data-node-df-id", topologyNodeId.split("-").pop());
            editor.editor_mode = "fixed";

            updateInputTimeseries();

            guiModal.show();
            if(copCollapseDOM){
                copCollapse.hide();
            }
            $('[data-bs-toggle="tooltip"]').tooltip();
        }).catch(error => {
            alert("Could not open node:\n"+error.message);
            console.error(error);
        });
    }
}
// endregion


/* onclick method associated to the save button of the modal */
function submitForm(e) {

    // get the parameters which uniquely identify the asset
    const assetTypeName = guiModalDOM.getAttribute("data-node-type");
    const topologyNodeId = guiModalDOM.getAttribute("data-node-topo-id"); // e.g. 'node-2'
    const drawflowNodeId = guiModalDOM.getAttribute("data-node-df-id");

    // get the node name field to update it if the form was submitted successfully
    const nodeName = document.getElementById(topologyNodeId).querySelector(".nodeName");
    const nodeNameValue = guiModalDOM.querySelector('input[df-name]').value;
    // get the data of the form
    const assetForm = e.target.closest('.modal-content').querySelector('form');
    const formData = new FormData(assetForm);

    // add the XY position of the node to the form data
    const nodePosX = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_x;
    const nodePosY = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_y;
    formData.set('pos_x', nodePosX);
    formData.set('pos_y', nodePosY);

    // if the asset is a bus, add the input and output ports to the form data
    if (assetTypeName === BUS) {
        const nodeInputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].inputs).length;
        const nodeOutputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].outputs).length;
        formData.set('input_ports', nodeInputs);
        formData.set('output_ports', nodeOutputs);
    }
    else {
        const nodeId = parseInt(topologyNodeId.split("-").pop());
        const input_output_mapping = getInputOutputMapping(nodeId);
        formData.set("inputs", input_output_mapping.inputs);
        formData.set("outputs", input_output_mapping.outputs);
    }

    // formPostUrl is defined in scenario_step2.html
    let postUrl = formPostUrl + assetTypeName;
    if (nodesToDB.has(topologyNodeId))
        postUrl += "/" + nodesToDB.get(topologyNodeId).uid;

    // send the form of the asset to be saved in database (projects/views.py::asset_create_or_update)
    fetch(postUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
        body: formData,
    }).then(response => response.json()).then(jsonRes => {
        if (jsonRes.success) {
            // rename the node on the fly (to avoid the need of refreshing the page)
            nodeName.textContent = nodeNameValue;

            // add the node id to the nodesToDB mapping
            if (!nodesToDB.has(topologyNodeId))
                nodesToDB.set(topologyNodeId, {uid:jsonRes.asset_id, assetTypeName: assetTypeName });

            guiModal.hide();
            if(copCollapseDOM){
                copCollapse.hide();
            }
        } else {
            // assign the content of the form to the form tag of the modal
            guiModalDOM.querySelector('form .modal-body').innerHTML = jsonRes.form_html;
        }
    }).catch(error => {
        console.error(error);
        alert(error.message);
    });
}


$("#guiModal").on('shown.bs.modal', _ => {
     var formDiv = document.getElementsByClassName("form-group");
     var plotDiv = null;

    //TODO get rid of maybe soc_traces
     var plotDivIds = ["flow_trace", "soc_traces"];

     for(i=0;i<plotDivIds.length;++i){
         plotDiv = document.getElementById(plotDivIds[i]);
         if (plotDiv){
            Plotly.relayout(plotDiv, {width: plotDiv.clientWidth});
         }
     }
     const evt = new Event("change");
	 // look only for the form with the provided class to be extra safe
	 document.querySelectorAll("input[name$='_scalar']").forEach(node => { node.dispatchEvent(evt); });
});

/* Triggered before the modal opens */
$("#guiModal").on('show.bs.modal', function (event) {
  var modal = $(event.target);
  // rename the node on the fly (to avoid the need of refreshing the page)
  const nodeName = guiModalDOM.querySelector('input[df-name]');
  if(nodeName){
    modal.find('.modal-title').text(nodeName.value.replaceAll("_", " "));
  }
});

/* Triggered before the modal hides */
$("#guiModal").on('hide.bs.modal', function (event) {
  // reset the modal form to empty
  guiModalDOM.querySelector('form .modal-body').innerHTML = "";
  editor.editor_mode = "edit";
});


/* Create node on the gui */
async function createNodeObject(nodeName, connectionInputs, connectionOutputs, nodeData, pos_x, pos_y) {
    // automate the naming of assets to avoid name duplicates
    const editorData = editor.export().drawflow.Home.data;
    const node_list = Object.values(editorData);
    const node_classes = node_list.map(obj => obj.class);
    let existing_items = node_classes.reduce((acc, name) => acc+name.includes(nodeName), 0);

    let shownName;
    if(typeof nodeData.name === "undefined"){
        if(existing_items == 0){
            shownName = nodeName + "-0";
        }
        else{
            shownName = nodeName + "-" + existing_items;
        }
        nodeData.name = shownName;
    }
    else{
        shownName = nodeData.name;
    }

    const source_html = `<div class="box" ${ASSET_TYPE_NAME}="${nodeName}">
    </div>

    <div class="drawflow-node__name nodeName">
        <span>
          ${shownName}
        </span>
    </div>
    <div class="img"></div>`;

    return {
        "editorNodeId": editor.addNode(nodeName, connectionInputs, connectionOutputs, pos_x, pos_y, nodeName, nodeData, source_html),
        "specificNodeType": nodeName
    };
}


/* Script to retrieve nodes (assets and busses) and links data from the backend. */
/* Html of asset modification is provided in grid_model_topology.js:createNodeObject function */
const addBusses = async (data) =>
    await Promise.all(data.map(async nodeData => {
        const result = await createNodeObject(nodeData.name, nodeData.input_ports, nodeData.output_ports, nodeData.data, nodeData.pos_x, nodeData.pos_y);
        nodesToDB.set(`node-${result.editorNodeId}`, {uid:nodeData.data.databaseId, assetTypeName: "bus" });
    }));

const addAssets = async (data) =>
    await Promise.all(data.map(async nodeData => {
        const result = await createNodeObject(nodeData.name, 1, 1, nodeData.data, nodeData.pos_x, nodeData.pos_y);
        nodesToDB.set(`node-${result.editorNodeId}`, {uid:nodeData.data.unique_id, assetTypeName: nodeData.name });
    }));

/* 'editor' is the variable name of the DrawFlow instance used here as a global variable */
const addLinks = async (data) => data.map(async linkData => {
    const busNodeId = [...nodesToDB.entries()].filter(([key,val])=>val.uid===linkData.bus_id).map(([k,v])=>k)[0].split("-").pop();
    const assetNodeId = [...nodesToDB.entries()].filter(([key,val])=>val.uid===linkData.asset_id).map(([k,v])=>k)[0].split("-").pop();
    if (linkData.flow_direction === "B2A")
        editor.addConnection(busNodeId, assetNodeId, linkData.bus_connection_port, 'input_1');
    else
        editor.addConnection(assetNodeId, busNodeId, 'output_1', linkData.bus_connection_port);
});
