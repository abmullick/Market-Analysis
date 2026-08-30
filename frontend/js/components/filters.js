export function renderFilters(container, filters) {
    if (!container) return;
    container.innerHTML = "";

    filters.forEach((filter) => {
        const wrapper = document.createElement("div");
        wrapper.className = "filter-group";

        const label = document.createElement("label");
        label.textContent = filter.label;
        wrapper.appendChild(label);

        let input;
        if (filter.type === "select") {
            input = document.createElement("select");
            input.name = filter.name;
            (filter.options || []).forEach((opt) => {
                const option = document.createElement("option");
                option.value = opt.value;
                option.textContent = opt.label;
                input.appendChild(option);
            });
        } else {
            input = document.createElement("input");
            input.type = filter.type || "text";
            input.name = filter.name;
            input.placeholder = filter.placeholder || "";
        }

        wrapper.appendChild(input);
        container.appendChild(wrapper);
    });
}
