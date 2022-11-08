// Constants
const ASSET_TYPE_NAME = 'asset_type_name';
const BUS = "bus";
// UUID to Drawflow Id Mapping
// const nodeToDbId = { 'bus': [], 'asset': [] };
const nodesToDB = new Map();


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

function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    ev.dataTransfer.setData("node", ev.target.getAttribute('data-node'));
}

function drop(ev) {
    ev.preventDefault();
    const nodeName = ev.dataTransfer.getData("node");
    (nodeName === BUS) ? IOBusOptions(nodeName, ev.clientX, ev.clientY)
        : addNodeToDrawFlow(nodeName, ev.clientX, ev.clientY);
}


function IOBusOptions(nodeName, posX, posY) {
    const checkMinMax = (value, min, max) => (value <= min) ? min : (value >= max) ? max : value;
    Swal.mixin({
        input: 'number',
        confirmButtonText: 'Next',
        showCancelButton: true,
        progressSteps: ['1', '2']
    })
        .queue([
            {
                title: 'Bus Inputs',
                text: 'Provide the number of bus Inputs (default 1)',
            },
            {
                title: 'Bus Outputs',
                text: 'Provide the number of bus Outputs (default 1)',
            }
        ])
        .then((result) => {
            if (result.value) {
                const inputs = checkMinMax(result.value[0], 1, 7);
                const outputs = checkMinMax(result.value[1], 1, 7);
                addNodeToDrawFlow(nodeName, posX, posY, inputs, outputs);
            }
        })
}


// Disallow Any Connection to be created without a bus.
editor.on('connectionCreated', function (connection) {
    var nodeIn = editor.getNodeFromId(connection['input_id']);
    var nodeOut = editor.getNodeFromId(connection['output_id']);
    if ((nodeIn['name'] !== BUS && nodeOut['name'] !== BUS) || (nodeIn['name'] === BUS && nodeOut['name'] === BUS)) {
        editor.removeSingleConnection(connection['output_id'], connection['input_id'], connection['output_class'], connection['input_class']);
        Swal.fire('Unexpected Connection', 'Please connect assets to each other\n only through a bus node. Interconnecting busses is also not allowed.', 'error')
    }
})

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
})

editor.on('nodeRemoved', function (nodeID) {
    // remove nodeID from nodesToDB
    nodesToDB.delete('node-'+nodeID);
})


async function addNodeToDrawFlow(name, pos_x, pos_y, nodeInputs = 1, nodeOutputs = 1, nodeData = {}) {
    if (editor.editor_mode === 'fixed')
        return false;
    // the following translation/transformation is required to correctly drop the nodes in the current clientScreen
    pos_x = pos_x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)) - (editor.precanvas.getBoundingClientRect().x * (editor.precanvas.clientWidth / (editor.precanvas.clientWidth * editor.zoom)));
    pos_y = pos_y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)) - (editor.precanvas.getBoundingClientRect().y * (editor.precanvas.clientHeight / (editor.precanvas.clientHeight * editor.zoom)));
    return createNodeObject(name, nodeInputs, nodeOutputs, {}, pos_x, pos_y);
}

// region Show Modal either by double clicking the box or the drawflow node.
var transform = '';

document.addEventListener("dblclick", function (e) {
    const openModal = function (box) {
        box.closest(".drawflow-node").style.zIndex = "9999";
        box.querySelector('.modal').style.display = "block";
        transform = editor.precanvas.style.transform;
        editor.precanvas.style.transform = '';
        editor.precanvas.style.left = editor.canvas_x + 'px';
        editor.precanvas.style.top = editor.canvas_y + 'px';
        editor.editor_mode = "fixed";
    }

    const closestNode = e.target.closest('.drawflow-node');
    const nodeType = closestNode.querySelector('.box').getAttribute(ASSET_TYPE_NAME);
    if (closestNode && closestNode.querySelector('.modal').style.display !== "block") {
        const topologyNodeId = closestNode.id;
        const getUrl = formGetUrl + nodeType +
            (nodesToDB.has(topologyNodeId) ? "/" + nodesToDB.get(topologyNodeId).uid : "");
        fetch(getUrl)
        .then(res=>res.text())
        .then(res=> {
            const formParentDiv = closestNode.querySelector('form').parentNode;
            // console.log(formParentDiv);
            formParentDiv.innerHTML = res;
            const box = formParentDiv.closest('.box');
            openModal(box);
        })
        //.catch(err => console.log("Modal get form JS Error: " + err));
    }
});
// endregion


// region close Modal on: 1. click 'x', 2. press 'esc' and 3. click outside the modal.
function closeModalSteps(modal) {
    // // Change the name of the node based on input
    const nodeNameElem = modal.closest('.drawflow_content_node').querySelector('.nodeName');
    nodeNameElem.textContent = `${modal.querySelector('input[df-name]').value}`;
    // End name change

    modal.style.display = "none"; // hide the modal
    modal.closest(".drawflow-node").style.zIndex =
        (modal.closest(".drawflow-node").classList.contains("ess")) ? "1" : "2"; // bring node to default z-index
    editor.precanvas.style.transform = transform;
    editor.precanvas.style.left = '0px';
    editor.precanvas.style.top = '0px';
    editor.editor_mode = "edit";

    // delete modal form
    modal.querySelector('form').parentNode.innerHTML = "<form></form>";
}

const closemodal = (e) => closeModalSteps(e.target.closest(".modal"));

const submitForm = (e) => {
    const assetForm = e.target.closest('.modal-content').querySelector('form');
    const assetTypeName = assetForm.closest('.box').getAttribute(ASSET_TYPE_NAME);
    const topologyNodeId = assetForm.closest('.drawflow-node').id; // e.g. 'node-2'
    const drawflowNodeId = topologyNodeId.split("-").pop();
    const postUrl = formPostUrl + assetTypeName
        + (nodesToDB.has(topologyNodeId) ? "/" + nodesToDB.get(topologyNodeId).uid : "");

    const formData = new FormData(assetForm);

    const nodePosX = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_x
    const nodePosY = editor.drawflow.drawflow.Home.data[drawflowNodeId].pos_y
    formData.set('pos_x', nodePosX);
    formData.set('pos_y', nodePosY);
    if (assetTypeName === BUS) {
        const nodeInputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].inputs).length
        const nodeOutputs = Object.keys(editor.drawflow.drawflow.Home.data[drawflowNodeId].outputs).length
        formData.set('input_ports', nodeInputs);
        formData.set('output_ports', nodeOutputs);
    }

    fetch(postUrl, {
        method: "POST",
        headers: {
            // 'Content-Type': 'multipart/form-data', //'application/json', // if enabled then read json.loads(request.body) in the backend
            "X-CSRFToken": csrfToken
        },
        body: formData,
    })
    .then(res=>res.json())
    .then(jsonRes=>{
        if (jsonRes.success) {
            if (nodesToDB.has(topologyNodeId) === false)
                nodesToDB.set(topologyNodeId, {uid:jsonRes.asset_id, assetTypeName: assetTypeName });
            closeModalSteps(e.target.closest(".modal"));
        } else {
            assetForm.innerHTML = jsonRes.form_html;
        }
    })
    .catch(err => console.log("Modal form JS Error: " + err));
}

// On Esc button press, close modal
document.addEventListener('keydown', function (e) {
    const modalList = document.getElementsByClassName("modal");
    if (e.keyCode === 27) {
        for (let modalDiv of modalList) {
            if (modalDiv.style.display === "block")
                closeModalSteps(modalDiv);
        }
    }
})

// When the user clicks anywhere outside of the modal, close it
window.onclick = function (e) {
    const modalList = document.getElementsByClassName("modal");
    for (const modalDiv of modalList) {
        if (e.target === modalDiv && modalDiv.style.display === "block")
            closeModalSteps(modalDiv);
    }
}
// endregion set


async function createNodeObject(nodeName, connectionInputs = 1, connectionOutputs = 1, nodeData = {}, pos_x, pos_y) {
    const shownName = (typeof nodeData.name === 'undefined') ? nodeName : nodeData.name;
    const source_html = `<div class="box" ${ASSET_TYPE_NAME}="${nodeName}">
        <div class="modal" style="display:none">
          <div class="modal-content">
            <span class="close" onclick="closemodal(event)">&times;</span>
            <br>
            <h2 class="panel-heading" text-align: left">${nodeName.replaceAll("_", " ")} Properties</h2>
            <br>
            <div class="row">
            <div class="col-md-1"></div>
            <div class="col-md-10">
                <form></form>
            </div>
            </div>
            <br>
            <div class="row">
                <div class="col-md-3"></div>
                <div class="col-md-6">
                ${scenarioBelongsToUser ? '<button class="modalbutton" style="font-size: medium; font-family: century gothic" onclick="submitForm(event)">Ok</button>': ''}
                </div>
            </div>
          </div>
        </div>
    </div>
    <div class="nodeName" >${shownName}</div>`;

    return {
        "editorNodeId": editor.addNode(nodeName, connectionInputs, connectionOutputs, pos_x, pos_y, nodeName, nodeData, source_html),
        "specificNodeType": nodeName
    };
}
