# PROJECT: Build a Professional 2D Graph and Diagram Editor for Windows and macOS

## 1. Your Role

Act as a senior software engineer, desktop application architect, UI/UX designer, computational geometry engineer, and mathematical software developer.

Your task is to design, implement, test, and deliver a complete, functional desktop application for Windows and macOS.

The application should combine the manual drawing precision and object manipulation of CAD software with the coordinate systems of mathematical graphing software and the flexibility required for economics diagrams.

This must be a real, usable application, not a mockup, a static demonstration, or a web page disguised as desktop software.

You must write actual working code, organize the project professionally, run it, test its features, fix errors, and provide clear installation and build instructions.

Do not stop after producing an architecture proposal or a basic prototype. Continue implementation until the core application is functional.

If a feature is particularly complex, implement a working version first and improve it incrementally rather than leaving it as a placeholder.

---

# 2. Core Concept

Create a desktop application for producing precise, manually constructed two-dimensional graphs and diagrams.

The application should be particularly suitable for:

- Mathematical graphs.
- Economics diagrams for the IB Economics curriculum.
- Supply and demand curves.
- Production possibility curves.
- Cost and revenue curves.
- Equilibrium diagrams.
- Indifference curves.
- Macroeconomic diagrams, including AD-AS and Keynesian models.
- Scatter plots and regression lines.
- Functions and their intersections.
- General coordinate-based diagrams.
- Engineering and scientific illustrations that use Cartesian coordinates.

The application should combine three complementary workflows:

1. **Manual drawing:** Users construct diagrams themselves, similarly to CAD software.
2. **Mathematical plotting:** Users enter mathematical functions and have the application generate their graphs.
3. **Data visualization:** Users enter datasets to generate scatter plots, regression lines, and related visualizations.

All three workflows must work within the same document and coordinate system.

For example, a user should be able to generate a mathematical demand curve, manually draw a supply curve, add an equilibrium point, draw dashed construction lines, and label the equilibrium price and quantity.

The user must retain control over every object, including its position, geometry, appearance, visibility, and label.

---

# 3. Platform and Technology Requirements

The application must run natively as a desktop application on:

- Windows 10 and Windows 11, where technically supported by the chosen framework.
- macOS on Apple Silicon and Intel Macs where supported by the selected dependencies.

Prefer a cross-platform architecture that allows most of the codebase to be shared between Windows and macOS.

Choose the most appropriate technology stack based on the requirements below.

Preferred considerations:

- C++ with Qt for a mature desktop interface and graphics architecture.
- Alternatively, another suitable cross-platform desktop framework if it provides a clear technical advantage.

The graphics system must support:
- Smooth zooming and panning.
- Precise object positioning.
- Vector-based geometry.
- High-resolution exports.
- Accurate coordinate transformations.
- Selection and editing of individual objects.
- A scalable canvas that does not become blurry when zoomed.

Do not make the core drawing engine depend on raster graphics.

Use a vector-based scene or equivalent architecture.

The application must work offline for its core functionality.

External services must not be required for ordinary drawing, mathematical plotting, saving, or exporting.

Before implementation, briefly explain the selected technology stack and why it is appropriate. Then proceed directly to implementation.

---

# 4. User Interface

Design a professional interface inspired by CAD applications, vector drawing programs, and mathematical graphing software.

The interface should be functional, precise, and visually restrained.

Avoid excessive gradients, unnecessary animations, oversized controls, and decorative interface elements that waste space.

## 4.1 Main window

The main window should contain:

### A. Top menu bar

Include:

- File
- Edit
- View
- Graph
- Insert
- Object
- Tools
- Window
- Help

Implement the relevant menu commands rather than displaying nonfunctional menu items.

### B. Main toolbar

Provide quick access to:

- Select.
- Pan.
- Point.
- Line.
- Polyline.
- Curve.
- Arrow.
- Text.
- Mathematical function.
- Scatter plot.
- Regression line.
- Undo.
- Redo.
- Zoom in.
- Zoom out.
- Fit graph to view.

### C. Drawing canvas

The central area should contain the graph and all drawing objects.

The canvas must support:
- Zooming with the mouse wheel or trackpad.
- Panning by dragging with an appropriate mouse gesture or modifier.
- Selecting individual objects.
- Moving objects.
- Editing object geometry.
- Displaying selection handles.
- Snapping to coordinates or other objects when enabled.

### D. Properties panel

When an object is selected, display its editable properties.

The properties panel should change depending on the selected object.

For example:
- A line should expose its endpoints, line style, thickness, and label.
- A point should expose its coordinates, marker style, and name.
- A curve should expose its control points or function definition.
- An arrow should expose its endpoints and arrowhead settings.
- An axis should expose its range, intervals, labels, and visibility.
- A text object should expose its content, font, size, alignment, and position.

### E. Object and layer panel

Provide a list of objects in the current graph.

Users should be able to:
- Rename objects.
- Select objects from the list.
- Hide or show objects.
- Lock objects against accidental editing.
- Delete objects.
- Reorder objects when drawing order matters.
- Group and ungroup objects where supported.

Use clear icons or visual indicators for object types and visibility states.

---

# 5. Coordinate System and Axes

The coordinate system is one of the most important parts of the application.

Every document should support a configurable Cartesian coordinate system.

## 5.1 Axis configuration

The user must be able to configure the horizontal and vertical axes independently.

Each axis should have settings for:

- Visibility.
- Positive direction.
- Negative direction.
- Minimum value.
- Maximum value.
- Major interval.
- Minor interval.
- Axis title.
- Tick marks.
- Numeric labels.
- Line thickness.
- Line style.
- Arrowheads.
- Axis position.
- Label placement.
- Grid visibility.
- Number formatting.

## 5.2 Axis direction modes

Provide at least two main coordinate-system modes.

**Mode A: Positive-only axes**

Display the positive X and Y directions, with the origin at the lower-left portion of the plotting area.

This mode is especially useful for economics diagrams.

The user must be able to adjust the visible ranges and the amount of space available around the graph.

**Mode B: Positive and negative axes**

Display all four quadrants of a Cartesian coordinate system.

The user must be able to specify independent positive and negative ranges for both axes.

The origin should be positioned according to the selected coordinate ranges.

Also allow the user to configure the axes independently where this is useful.

## 5.3 Axis arrowheads

Allow the user to choose between:

- No arrowheads.
- An arrowhead at the positive end.
- An arrowhead at the negative end.
- Arrowheads at both ends.

Support independent settings for the X and Y axes.

Axis arrowheads must be rendered cleanly and remain correctly sized at different zoom levels.

## 5.4 Axis intervals and numeric labels

Allow the user to choose:

- Automatic intervals.
- Manually specified intervals.
- Major intervals only.
- Major and minor intervals.
- Tick marks without numeric labels.
- Numeric labels without visible gridlines.
- No intervals or tick marks.

For example, an economics graph might use intervals of 1, 5, or 10, while a mathematical graph might use intervals of 0.1 or π-based labels.

Where practical, support configurable numeric formatting, including decimal places, scientific notation, and common symbolic labels such as π.

## 5.5 Independent visibility controls

Provide independent visibility controls for:

- X-axis.
- Y-axis.
- Origin marker.
- Origin label.
- X-axis numeric labels.
- Y-axis numeric labels.
- X-axis tick marks.
- Y-axis tick marks.
- Major gridlines.
- Minor gridlines.
- Axis titles.
- Object labels.
- Points.
- Lines.
- Curves.
- Arrows.
- Construction lines.
- Individual objects.

Hiding an element must not delete it or alter the underlying geometry.

The origin must be independently configurable. For example, the user should be able to hide the origin marker while keeping the axes visible.

The user should also be able to hide both axes while retaining the coordinate system internally, allowing objects to be drawn using mathematical coordinates without displaying the axes in the final export.

## 5.6 Grid and snapping

Support:
- Major and minor grids.
- Optional grid snapping.
- Configurable snapping intervals.
- Optional snapping to existing points.
- Optional snapping to endpoints and intersections.
- A visual indicator when snapping occurs.

Snapping must be optional. Users must always be able to draw freely when precision snapping is not wanted.

---

# 6. CAD-Like Manual Drawing

Manual drawing is the application's defining feature.

Users must be able to construct diagrams freely rather than being restricted to mathematically generated functions.

The application must behave similarly to a lightweight 2D CAD or vector drawing program.

Objects should be created, selected, moved, edited, renamed, hidden, and deleted independently.

## 6.1 Selection tool

Implement a selection tool that supports:
- Selecting objects by clicking.
- Selecting multiple objects.
- Dragging objects to new positions.
- Moving selected objects using keyboard shortcuts.
- Editing geometry using control handles.
- Selecting objects through the object panel.
- Deleting selected objects.
- Copying and pasting objects.
- Duplicating objects.
- Grouping and ungrouping objects.

Provide a clear visual indication of selection.

Where possible, distinguish between selecting an object and editing its geometry.

## 6.2 Points

Allow users to place points anywhere on the canvas.

Points should be defined internally by their mathematical coordinates, not merely by their screen positions.

Each point should support:
- X coordinate.
- Y coordinate.
- Optional name.
- Optional coordinate label.
- Marker shape.
- Marker size.
- Fill and outline styles.
- Visibility.
- Locking.
- Label position.
- Label font and size.

Example point names:
- A
- B
- E
- Equilibrium
- Maximum
- Minimum

The user should be able to select a point and edit its coordinates numerically.

Provide an option to display coordinates next to a point.

If a point is named A, the application should allow the displayed label to be either "A", "(3, 5)", or "A (3, 5)", depending on user preferences.

## 6.3 Straight lines and line segments

Provide tools for creating:
- Infinite straight lines.
- Finite line segments.
- Horizontal lines.
- Vertical lines.
- Polylines.

The user should be able to define a line by clicking its endpoints or entering coordinates numerically.

For line segments and polylines, support:
- Moving individual endpoints.
- Adding or removing vertices.
- Editing coordinates.
- Changing line thickness.
- Changing line style.
- Setting line color.
- Assigning a name or label.
- Hiding or showing the object.

Support solid, dashed, dotted, and dash-dot line styles.

For infinite lines, render only the portion intersecting the visible viewport.

## 6.4 Freeform curves

Provide tools for manually creating curves without requiring a mathematical equation.

The user should be able to draw a curve by clicking and dragging, placing control points, or editing an existing curve.

Use an appropriate vector curve representation, such as Bézier curves or splines.

Support:
- Adding control points.
- Moving control points.
- Adjusting curve shape.
- Extending a curve.
- Editing individual segments.
- Changing line style and thickness.
- Assigning a curve name.
- Showing or hiding the curve.

Curve editing must remain smooth and predictable.

A curve must be a real editable vector object rather than a raster image.

Where feasible, support both smooth curves and curves passing through user-defined points.

## 6.5 Arrows

Implement arrows with behavior closely matching the arrow tool in Microsoft Paint.

This is an explicit design requirement.

The user should:
1. Select the arrow tool.
2. Click at the starting point.
3. Drag to the endpoint.
4. Release the mouse button to create the arrow.

The resulting arrow should be a straight line with an arrowhead at its endpoint.

The arrow should follow the drag direction and have predictable geometry.

Support:
- Adjustable line thickness.
- Configurable arrowhead size.
- Line color.
- Line style.
- Endpoint editing.
- Moving the entire arrow.
- Naming and labeling.
- Visibility controls.

The default arrowhead should resemble a conventional filled triangular arrowhead.

Do not substitute a complicated multi-click workflow for this familiar drag-to-draw interaction.

Where possible, provide optional start and end arrowheads as additional settings.

## 6.6 Text and labels

Provide a text tool for placing arbitrary text anywhere on the canvas.

Support:
- Text content.
- Font family.
- Font size.
- Bold and italic.
- Alignment.
- Rotation.
- Text color.
- Position.
- Optional background.
- Editing after placement.

Text objects must support mathematical notation where practical.

Users should be able to add labels such as:
- Price
- Quantity
- MC
- MR
- Demand
- Supply
- Real GDP
- Price Level
- Equilibrium Price
- Equilibrium Quantity

Text must remain legible at normal export sizes.

## 6.7 Object names versus displayed labels

Every object should have an internal name and, where appropriate, a separate visible label.

For example:
- Internal name: DemandCurve
- Visible label: D

A user should be able to rename an object without necessarily changing its visible label.

Object names should appear in the object panel.

Visible labels should appear on the graph only when enabled.

For curves and lines, allow labels to be positioned manually. Where feasible, also support attaching a label to a specific point along a curve so that it follows the curve when the geometry changes.

---

# 7. Mathematical Function Plotter

Include a mathematical graph generator inspired by the function-entry workflow of Desmos.

This feature should coexist with the manual drawing tools.

Users should be able to create graphs from mathematical expressions without writing programming code.

## 7.1 Function input

Provide a function list or equation editor where users can enter expressions such as:

y = 2x + 3

y = x^2

y = -0.5x + 8

y = sin(x)

y = sqrt(x)

y = ln(x)

y = 1/x

The application should parse the expressions and plot the corresponding functions over the visible coordinate range.

Support, at minimum, common operations and functions:
- Addition.
- Subtraction.
- Multiplication.
- Division.
- Exponentiation.
- Parentheses.
- Square roots.
- Absolute values.
- Exponential functions.
- Natural and common logarithms.
- Trigonometric functions.
- Inverse trigonometric functions.
- Basic constants such as π and e.

Clearly document whether trigonometric inputs use radians or degrees. Radians should be the default, with a configurable alternative if practical.

## 7.2 Function properties

Each function should have:
- An expression.
- A unique internal name.
- An optional displayed label.
- A color.
- A line thickness.
- A line style.
- A visibility toggle.
- An optional domain restriction.
- Optional minimum and maximum values.

Users must be able to edit the expression after creation.

If an expression is invalid, display a useful error message without crashing the application.

## 7.3 Mathematical plotting accuracy

The plotting engine must handle:
- Discontinuities.
- Undefined regions.
- Vertical asymptotes.
- Domain restrictions.
- Negative values.
- Large coordinate ranges.
- Functions with steep gradients.
- Smooth curves at different zoom levels.

Do not connect samples across discontinuities or undefined regions.

Use adaptive sampling or another suitable numerical plotting technique to avoid visibly inaccurate curves.

The application should distinguish between a mathematical function and a manually drawn curve, even if both appear similar.

A mathematical function should retain its expression and regenerate its geometry when the expression or coordinate range changes.

A manually drawn curve should retain its manually edited geometry.

## 7.4 Function intersections and analysis

Where feasible, provide optional tools for finding:
- X-intercepts.
- Y-intercepts.
- Intersections between functions.
- Local maxima and minima.
- Derivatives.
- Numerical coordinates at a selected position.

Do not allow optional analysis tools to interfere with the basic plotting workflow.

---

# 8. Economics Diagram Workflow

Economics diagrams should be treated as a first-class use case, not as an afterthought.

The application should make it possible to create professional economics diagrams quickly.

Include useful drawing features such as:
- Demand curves.
- Supply curves.
- Marginal cost curves.
- Average cost curves.
- Revenue curves.
- Aggregate demand.
- Aggregate supply.
- Production possibility curves.
- Indifference curves.
- Budget lines.
- Equilibrium points.
- Dashed construction lines.
- Arrows indicating shifts.
- Labels placed directly beside curves.
- Price and quantity labels on axes.

These should primarily be created using the same general drawing tools as other objects.

Do not unnecessarily restrict the application to a predefined list of economics diagrams.

## 8.1 Construction lines

Provide a convenient way to create horizontal and vertical dashed lines.

For example, after selecting an equilibrium point, the user should be able to create:
- A vertical dashed line down to the X-axis.
- A horizontal dashed line across to the Y-axis.

The user must remain able to adjust the endpoints manually.

Where feasible, offer an optional command that automatically creates construction lines from a selected point to the axes.

## 8.2 Diagram templates

Provide optional starting templates, including:
- Basic positive-quadrant economics graph.
- Standard four-quadrant Cartesian graph.
- Supply and demand.
- AD-AS.
- Production possibility curve.
- Cost and revenue diagram.
- Blank coordinate system.
- Blank drawing canvas.

Templates should be starting configurations rather than restrictive diagram editors.

Users must be able to modify every object in a template.

## 8.3 Economics-friendly axis settings

Make it easy to configure:
- X-axis title: Quantity.
- Y-axis title: Price.
- Positive-only axes.
- Axis arrows.
- No gridlines.
- Custom intervals.
- Manually positioned curve labels.
- Dashed construction lines.

The user should be able to save a preferred configuration as a reusable template.

---

# 9. Scatter Plots and Regression

Implement basic data visualization.

Users should be able to create scatter plots by entering data manually or importing a CSV file.

## 9.1 Data input

Provide a table with two columns:
- X
- Y

Users should be able to:
- Add rows.
- Edit cells.
- Delete rows.
- Paste tabular data.
- Import CSV files.
- Name the dataset.
- Assign a label to the dataset.

Validate imported data and clearly identify invalid entries.

## 9.2 Scatter plots

Generate a scatter plot from the dataset.

Support:
- Point size.
- Marker shape.
- Color.
- Optional point labels.
- Axis configuration.
- Visibility controls.

The points should be represented as individual editable objects or as members of an editable dataset.

Users should be able to choose between keeping a dataset linked to its generated scatter plot and converting its points into independent drawing objects.

## 9.3 Regression lines

Provide at least linear least-squares regression.

Calculate the regression equation from the dataset and display it.

For a linear model, report:
- Slope.
- Intercept.
- Equation.
- Coefficient of determination, R².

Provide a regression-line visibility toggle.

The regression line should update automatically when the underlying dataset changes.

Where practical, offer polynomial regression as an optional extension.

Clearly distinguish between a statistically calculated regression line and a manually drawn line.

Do not claim statistical accuracy unless the calculations have been implemented and tested.

---

# 10. Object Editing and Precision

Precision is essential.

All geometry should be represented internally using mathematical coordinates, with the screen used only for rendering and interaction.

Implement a reliable transformation between:
- Mathematical coordinates.
- Canvas coordinates.
- Export coordinates.

The application must preserve object positions when zooming or panning.

Provide numerical editing for relevant objects.

Examples:
- Set a point to (4, 7).
- Set a line endpoint to (-2, 5).
- Set an axis range to -10 through 10.
- Set a function domain to 0 through 20.

Provide an optional status display showing the current cursor coordinates.

Where practical, support:
- Coordinate snapping.
- Grid snapping.
- Endpoint snapping.
- Intersection snapping.
- Keyboard movement.
- Object duplication.
- Alignment tools.

The coordinate transformation and drawing engine should be designed to minimize floating-point and rounding errors.

---

# 11. Undo, Redo, and Editing Reliability

Implement a proper undo/redo system.

Users should be able to reverse and restore actions such as:
- Creating an object.
- Deleting an object.
- Moving an object.
- Editing geometry.
- Changing an object's appearance.
- Changing axis settings.
- Editing a mathematical expression.
- Changing object visibility.
- Importing a dataset.

Use a coherent command or transaction architecture so that related changes can be undone reliably.

Avoid implementations where undo only works for a few specific tools.

Provide standard keyboard shortcuts, adapted appropriately for Windows and macOS.

---

# 12. Saving and Document Format

Create a native project file format.

The file should preserve:
- All drawing objects.
- Mathematical expressions.
- Coordinate ranges.
- Axis settings.
- Object names and labels.
- Visibility settings.
- Layers.
- Dataset values.
- Regression configuration.
- Styling.
- Document metadata.

The project file must allow the user to close the application and later continue editing without losing information.

Prefer a documented, versioned format based on a suitable structured representation, such as JSON, with a dedicated file extension.

For example:

`.graphproj`

The exact extension can be changed if a more appropriate design is selected.

The format should be designed to support future application updates.

Implement:
- New document.
- Open project.
- Save.
- Save As.
- Unsaved-change warnings.
- Recent documents where practical.
- File error handling.

Do not confuse exporting an image with saving an editable project.

---

# 13. Export Requirements

Export is a core requirement.

The application must support PNG, PDF, and DWG.

These formats serve different purposes and must be implemented appropriately.

## 13.1 PNG export

Support exporting the complete graph as a PNG image.

Include:
- Configurable image dimensions.
- High-resolution rendering.
- Transparent or solid background.
- Optional axes and gridlines.
- Optional labels.
- Optional margins.
- Appropriate antialiasing.

The exported image should not include editor controls, selection handles, toolbars, or other interface elements.

Allow the user to choose whether to export the complete document or a selected region.

Where possible, provide a preview before export.

## 13.2 PDF export

Generate a clean PDF containing the graph.

Prefer vector-based PDF output so that lines, text, and curves remain sharp when enlarged.

Preserve:
- Line styles.
- Arrowheads.
- Text.
- Coordinate axes.
- Labels.
- Mathematical curves.
- Page dimensions.
- Background settings.

Provide page-size options such as A4 and Letter, plus a custom page size.

Allow the user to choose portrait or landscape orientation.

Automatically fit the graph to the page while maintaining appropriate proportions.

Avoid unnecessary page margins or clipping.

## 13.3 DWG export

DWG export is required, but it must be implemented realistically.

DWG is a proprietary CAD format, so do not assume that an arbitrary drawing library can write fully compatible DWG files.

Investigate a technically legitimate solution.

Possible approaches include:
- An established CAD SDK with suitable licensing.
- A reliable conversion pipeline through a supported interchange format.
- A clearly documented optional dependency where direct DWG generation is not practical without it.

If direct DWG export requires an external SDK, investigate licensing, redistribution, platform compatibility, and build requirements before choosing it.

Do not silently substitute DXF for DWG while claiming DWG support.

If an intermediate DXF export is used, label it accurately and provide it as an additional format.

Where technically feasible, export:
- Lines as CAD line entities.
- Polylines as CAD polylines.
- Circles and points as suitable CAD entities.
- Text as CAD text entities.
- Arrows as line and arrowhead geometry.
- Curves as appropriate spline or polyline entities.
- Axes as CAD line entities.
- Gridlines as separate entities where enabled.

Preserve meaningful geometry rather than exporting the entire graph as a single raster image.

Investigate how to represent mathematical curves in CAD exports, and document any approximation necessary for compatibility.

The exported DWG must open in compatible CAD software.

If fully native DWG export cannot be delivered immediately, implement the rest of the application and provide a working additional DXF export while clearly documenting what is needed to enable DWG export.

Do not allow the DWG requirement to block completion of the drawing application.

## 13.4 Additional useful formats

If practical, also support:
- SVG.
- DXF.

SVG is particularly useful for vector graphics, while DXF can provide a useful CAD interchange format.

These formats are optional additions, not substitutes for the required PNG, PDF, and DWG support.

---

# 14. Appearance and Styling

Provide a coherent style system.

Objects should support configurable:
- Color.
- Line thickness.
- Line style.
- Opacity where appropriate.
- Marker size.
- Text font.
- Text size.
- Arrowhead style.
- Fill color where applicable.

Include a small set of sensible default colors and allow custom colors.

The application should produce diagrams suitable for:
- School assignments.
- Scientific reports.
- Economics examinations and coursework.
- University work.
- Technical documentation.
- Presentations.

The exported result should look clean and intentional, not like a screenshot of a drawing program.

Avoid automatically adding visual decorations that are inappropriate for academic diagrams.

---

# 15. Keyboard Shortcuts

Implement intuitive keyboard shortcuts.

At minimum, consider:

- Ctrl/Cmd + N: New document.
- Ctrl/Cmd + O: Open.
- Ctrl/Cmd + S: Save.
- Ctrl/Cmd + Shift + S: Save As.
- Ctrl/Cmd + Z: Undo.
- Ctrl/Cmd + Shift + Z: Redo, where consistent with platform conventions.
- Ctrl/Cmd + C: Copy.
- Ctrl/Cmd + V: Paste.
- Ctrl/Cmd + D: Duplicate, if appropriate.
- Delete/Backspace: Delete selected objects.
- Escape: Cancel the current drawing operation.
- V: Select tool.
- P: Point tool.
- L: Line tool.
- A: Arrow tool.
- T: Text tool.

Avoid shortcut conflicts with text input or operating-system conventions.

Allow shortcut assignments to be extended in the future.

---

# 16. Architecture and Code Quality

Structure the application as a maintainable software project.

Separate responsibilities into appropriate components, such as:

- Application startup and lifecycle.
- Main window and interface.
- Canvas and rendering.
- Coordinate system.
- Drawing tools.
- Geometry and object models.
- Selection and manipulation.
- Mathematical expression parsing.
- Function sampling and plotting.
- Data import and regression.
- Document serialization.
- Undo/redo.
- Export.
- Settings and preferences.

Use appropriate abstractions and avoid putting the entire application in one enormous source file.

The geometry model should be independent of the user interface wherever practical.

Avoid unnecessary dependencies.

Use well-maintained libraries with licenses compatible with the intended distribution.

Document any dependency whose licensing affects commercial use or redistribution.

Handle errors explicitly. Invalid mathematical expressions, corrupt files, invalid CSV data, and failed exports must not crash the application.

---

# 17. Testing Requirements

Do not consider the project complete merely because it compiles.

Implement and execute automated tests wherever practical.

At minimum, test:

### Coordinate system
- Positive-only axes.
- Four-quadrant axes.
- Independent X and Y ranges.
- Axis intervals.
- Origin positioning.
- Coordinate-to-screen transformations.

### Drawing
- Point creation and movement.
- Line creation and editing.
- Arrow direction and geometry.
- Curve creation and control-point editing.
- Object selection.
- Object visibility.
- Object naming.
- Numerical coordinate editing.

### Mathematical plotting
- Linear functions.
- Quadratic functions.
- Trigonometric functions.
- Domain restrictions.
- Invalid expressions.
- Discontinuities.
- Zooming and resampling.

### Data visualization
- CSV import.
- Invalid data handling.
- Scatter plots.
- Linear regression.
- Regression statistics.
- Updating a regression line when data changes.

### Document handling
- Save and reopen.
- Preservation of object geometry.
- Preservation of visibility and styling.
- Preservation of mathematical expressions.
- Preservation of datasets.
- Undo and redo.

### Export
- PNG dimensions and appearance.
- PDF rendering.
- Vector preservation in PDF where intended.
- CAD interchange geometry.
- DWG compatibility when DWG support is implemented.

Report which tests passed and which remain incomplete.

Do not claim a test passed unless it was actually executed.

---

# 18. Development Workflow

Work in the following phases.

## Phase 1: Technical foundation

1. Inspect the available development environment.
2. Select the technology stack.
3. Establish the project structure.
4. Implement the main window.
5. Implement the vector-based canvas.
6. Implement coordinate transformations.
7. Implement the axes and grid.
8. Verify that the application runs.

## Phase 2: Manual drawing

Implement:
1. Selection and manipulation.
2. Points.
3. Straight lines.
4. Polylines.
5. Arrows.
6. Freeform curves.
7. Text.
8. Object labels and names.
9. Visibility controls.
10. Properties panel.
11. Object panel.

Test each tool before proceeding.

## Phase 3: Document handling

Implement:
1. Native document format.
2. Save and open.
3. Undo and redo.
4. Copy and paste.
5. Keyboard shortcuts.
6. Error handling.

## Phase 4: Mathematical plotting

Implement:
1. Expression parsing.
2. Function plotting.
3. Domain restrictions.
4. Mathematical curve styling.
5. Function visibility.
6. Optional intersection and analysis tools.

## Phase 5: Data visualization

Implement:
1. Data table.
2. CSV import.
3. Scatter plots.
4. Linear regression.
5. Regression statistics.
6. Automatic updates.

## Phase 6: Export

Implement and test:
1. PNG.
2. PDF.
3. DXF if supported by the chosen architecture.
4. DWG through a legitimate, documented implementation.

## Phase 7: Finalization

1. Fix bugs.
2. Improve interface consistency.
3. Verify saving and reopening.
4. Test all essential tools.
5. Build the application for Windows.
6. Build the application for macOS.
7. Document the build process.
8. Prepare installation instructions.

If platform-specific packaging cannot be completed in the current environment, provide a reproducible build configuration and exact instructions for building on the missing platform.

Do not claim to have built or tested an operating-system version that you could not actually build or test.

---

# 19. Minimum Viable Product

Prioritize a complete and reliable initial version.

The first usable release must include:

1. A working desktop window.
2. A vector-based 2D canvas.
3. Configurable X and Y axes.
4. Positive-only and four-quadrant coordinate modes.
5. Configurable intervals and arrowheads.
6. Independent axis, label, origin, and grid visibility.
7. Manual points.
8. Manual lines and line segments.
9. Freeform curves.
10. Microsoft Paint-style drag-to-draw arrows.
11. Text and labels.
12. Names for points, lines, curves, and axes.
13. An object list and properties panel.
14. Zooming and panning.
15. Undo and redo.
16. Saving and reopening editable documents.
17. PNG export.
18. PDF export.

The mathematical function plotter and scatter/regression functionality are also important project requirements. Implement them after the core editor is stable.

DWG export must be investigated from the beginning because its technical and licensing constraints may affect the architecture.

If development time or environment limitations prevent implementing every feature simultaneously, deliver the complete minimum viable product first, then continue expanding it.

Never represent an unimplemented feature as finished.

---

# 20. Acceptance Criteria

The project is successful only when a user can perform the following workflow:

1. Open the application.
2. Create a new graph.
3. Choose positive-only axes or a four-quadrant coordinate system.
4. Configure the axis ranges and intervals.
5. Hide or show individual axis elements.
6. Draw a straight line manually.
7. Draw a curve manually.
8. Create an arrow by dragging from its starting point to its endpoint, as in Microsoft Paint.
9. Place and name points.
10. Name lines and curves.
11. Add text labels.
12. Select, move, edit, and delete individual objects.
13. Save the document.
14. Close and reopen the document without losing its contents.
15. Export the graph as a clean PNG image.
16. Export the graph as a clean PDF.
17. Generate a curve from a mathematical function.
18. Import data and generate a scatter plot.
19. Calculate and display a linear regression line.
20. Export CAD-compatible geometry and, where the required implementation is available, a valid DWG file.

The interface must remain responsive during normal use.

Objects must preserve their positions and geometry during zooming, panning, saving, reopening, and exporting.

---

# 21. Final Instructions

Start by briefly presenting the proposed architecture and technology stack.

Then begin implementing the actual application.

Do not spend excessive time discussing theoretical alternatives.

Do not provide only pseudocode, screenshots, UI mockups, or isolated examples.

Create the actual project files, run the application, test the implementation, and correct any problems you encounter.

Use sensible engineering judgment when details are unspecified, but do not silently remove major requirements.

If a requirement cannot be implemented because of technical, licensing, or environment limitations, explain the precise limitation and provide the closest technically legitimate solution.

Keep the project organized so that another developer can continue working on it.

At completion, provide:
- The project source code.
- A list of implemented features.
- A list of known limitations.
- Test results.
- Dependency and licensing information.
- Windows build instructions.
- macOS build instructions.
- Instructions for running the application.
- Instructions for producing distributable installers.
- A clear statement of whether PNG, PDF, DXF, and DWG exports were actually implemented and tested.

**The objective is a practical, polished, extensible 2D graph and diagram editor that combines CAD-like manual construction with mathematical graphing and statistical plotting.**