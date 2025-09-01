# ROI-Price-Calculator
Price calculator based on return on investment (ROI) for the KAWA corporation in the Prosperous Universe online game.

# Approach to calcuation

## Price
The price of any item can be broken down into multiple parts.  I start by breaking the price ($P_{price}$) into $P_{price}=P_{profit}+C_{repairs}+C_{inputs}+C_{population}$.

* $P_{profit}$: The desired profit for any given item.  Our desired profit is based on ROI.  However, this could be calulated another way.
* $C_{repairs}$: The cost of repairs.
* $C_{inputs}$: The cost of input materials to the recipe.
* $C_{population}$: The cost of feeding your population needs (e.g., pioneers and/or settlers).

### Price as a weighted sum of population costs
The population cost ($C_{population}$) can be realized as a weighted sum of each type of popluation (WSP): $C_{population}=A*C_{PIO}+B*C_{SET}+C*C_{TEC}+D*C_{ENG}+E*C_{SCI}$.
* $C_{PIO/SET/TEC/ENG/SCI}$: Cost to support a single (Pioneer/Settler/Technician/Engineer/Scientist) per unit time (ms in my calculations).
* $A/B/C/D/E$: Product of the number of (Pioneers/Settlers/Technicians/Engineers/Scientists) with the amount of time needed to support each for the given recipe.

All parts of the $P_{price}$ equation can also be represented by a WSP.  Using this representation, a $P_{price}$ (as a WSP) can be calculated without assuming a price for any material.

### Iterative solution
The $C_{population}$ WSP can be calculated for any recipe.  The recipe specifies the population required (indirectly through its building type) and the time it takes to complete the recipe.  Some recipes also require a specific planet to be chosen for its natural abundance of a natural resource or its fertility.  This is used to initialize a price for all materials.

Each iteration updates the WSP $P_{price}$, $P_{profit}$, $C_{repairs}$ and $C_{inputs}$ until any changes to $P_{price}$ for all materials is under a given threshold.

### Final Price
The final price is calculated from the WSP $P_{price}$ of consumables.