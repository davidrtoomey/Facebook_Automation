1. simplify everything. delete everything down to its essence. only what's needed.
2. The automation dashboard control panel is too cluttered. I need advice how to simplify the control panel and make it stupid simple for the user.
3. Add ebay API so the user can enter any search term, and the offer_agent.py can dynamically look at sold listings on eBay (average the 3 sold listings that most resemble the listing) of them item in its current condition and accurately send offers on any item even if it's not an iPhone.
4. add the ability for the offer_agent to identify, label, and accurately quote listings that are selling more than one item. for example a listing with an iPhone 14 pro max AND an iPad pro 6th gen 12.9 inch cellular. 
5. tackle packaging & distribution, updates etc.



(complete)1. Next I need to try replacing the first agent call in offer_agent.py with just a playwright call so then each time process_single_url gets called it has a new memory state (smaller context and less confusion).
