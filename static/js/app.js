let openShopping = document.querySelector('.shopping');
let closeShopping = document.querySelector('.closeShopping');
let list = document.querySelector('.list');
let listCard = document.querySelector('.listCard');
let body = document.querySelector('body');
let total = document.querySelector('.total');
let quantity = document.querySelector('.quantity');

openShopping.addEventListener('click', () => {
  body.classList.add('active');
});

closeShopping.addEventListener('click', () => {
  body.classList.remove('active');
});

list.addEventListener('change', (event) => {
  if (event.target.matches('.itemCheckbox')) {
    toggleCardItem(event.target);
  }
});
function toggleCardItem(checkbox) {
  const card = document.getElementById('card');
  const listCard = card.querySelector('.listCard');

  const row = checkbox.parentNode.parentNode;
  const columns = row.getElementsByTagName('td');

  const description = columns[1].textContent; // Assuming the description is in the 2nd column
  const preco = columns[4].textContent; // Assuming the preco is in the 5th column
  const precoFinalInput = row.querySelector('.preco-input');
  const precoFinal = precoFinalInput.value.trim();

  if (checkbox.checked) {
    const existingItem = listCard.querySelector(`li[data-description="${description}"]`);
    if (existingItem) {
      const numElement = existingItem.querySelector('.numeros');
      let nume = parseInt(numElement.textContent);
      numElement.textContent = nume.toString();
    } else {
      const item = document.createElement('li');
      item.dataset.description = description;

      const itemName = document.createElement('div');
      itemName.textContent = description; // Set the item description
      item.appendChild(itemName);

      const precoElement = document.createElement('span');
      precoElement.textContent = precoFinal || preco; // Use precoFinal if not empty, otherwise use preco
      item.appendChild(precoElement);

      const decreaseButton = document.createElement('button');
      decreaseButton.textContent = '-';
      decreaseButton.addEventListener('click', () => {
        let nume = parseInt(numElement.textContent);
        if (nume > 1) {
          nume--;
          numElement.textContent = nume.toString();
          updateTotal(); // Update the total value
        } else {
          listCard.removeChild(item);
          checkbox.checked = false;
          updateTotal(); // Update the total value
          toggleRowColor(checkbox); // Update the row color and quantity
        }
      });
      item.appendChild(decreaseButton);

      const numElement = document.createElement('div');
      numElement.classList.add('numeros');
      numElement.textContent = '1';
      item.appendChild(numElement);

      const increaseButton = document.createElement('button');
      increaseButton.textContent = '+';
      increaseButton.addEventListener('click', () => {
        let nume = parseInt(numElement.textContent);
        nume++;
        numElement.textContent = nume.toString();
        updateTotal(); // Update the total value
      });
      item.appendChild(increaseButton);

      listCard.appendChild(item);
    }
  } else {
    const existingItem = listCard.querySelector(`li[data-description="${description}"]`);

    if (existingItem) {
      listCard.removeChild(existingItem);
      var cardItem = checkbox.parentNode.parentNode;
      var cardList = document.querySelector(".listCard");
      cardList.removeChild(cardItem);
      checkbox.checked = false;

      if (listCard.children.length === 0) {
        card.style.display = 'none'; // Hide the card when it has no items
      }
    }

    // Reset the div.numeros to 0
    const numElement = row.querySelector('.numeros');
    numElement.textContent = '0';
  }

  updateTotal(); // Update the total value
}

function toggleRowColor(checkbox) {
  var row = checkbox.parentNode.parentNode;
  var quantitySpan = document.querySelector(".quantity");

  if (checkbox.checked) {
    row.classList.add("selected");
    quantitySpan.innerText = parseInt(quantitySpan.innerText) + 1;
  } else {
    row.classList.remove("selected");
    var currentQuantity = parseInt(quantitySpan.innerText);
    updateTotal()
    if (currentQuantity > 0) {
      quantitySpan.innerText = currentQuantity - 1;
    }
  }
}

function updateTotal() {
  const listCard = document.querySelector('.listCard');
  const items = listCard.querySelectorAll('li');
  let totalValue = 0;

  items.forEach((item) => {
    const numElement = item.querySelector('.numeros');
    const precoElement = item.querySelector('span');
    const quantity = parseFloat(numElement.textContent.replace(/[^0-9.,]+/g, '').replace(',', '.'));
    const price = parseFloat(precoElement.textContent.replace(/[^0-9.,]+/g, '').replace(',', '.'));

    totalValue += quantity * price;
  });
  
  total.textContent = 'R$ ' + totalValue.toFixed(3); // Set the total value with two decimal places and format it as "R$ 23,822.00"
}

function formatNumber(number) {
  const options = {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  };
  const formattedNumber = number.toLocaleString('pt-BR', options);
  return formattedNumber.replace(',', '.'); // Replace the decimal separator with a comma
}

// let products = [
//     {
//         id: 1,
//         name: 'PRODUCT NAME 1',
//         image: '1.PNG',
//         price: 120000
//     },
//     {
//         id: 2,
//         name: 'PRODUCT NAME 2',
//         image: '2.PNG',
//         price: 120000
//     },
//     {
//         id: 3,
//         name: 'PRODUCT NAME 3',
//         image: '3.PNG',
//         price: 220000
//     },
//     {
//         id: 4,
//         name: 'PRODUCT NAME 4',
//         image: '4.PNG',
//         price: 123000
//     },
//     {
//         id: 5,
//         name: 'PRODUCT NAME 5',
//         image: '5.PNG',
//         price: 320000
//     },
//     {
//         id: 6,
//         name: 'PRODUCT NAME 6',
//         image: '6.PNG',
//         price: 120000
//     }
// ];
// let listCards  = [];
// function initApp(){
//     products.forEach((value, key) =>{
//         let newDiv = document.createElement('div');
//         newDiv.classList.add('item');
//         newDiv.innerHTML = `
//             <img src="image/${value.image}">
//             <div class="title">${value.name}</div>
//             <div class="price">${value.price.toLocaleString()}</div>
//             <button onclick="addToCard(${key})">Add To Card</button>`;
//         list.appendChild(newDiv);
//     })
// }
// initApp();
// function addToCard(key){
//     if(listCards[key] == null){
//         // copy product form list to list card
//         listCards[key] = JSON.parse(JSON.stringify(products[key]));
//         listCards[key].quantity = 1;
//     }
//     reloadCard();
// }
// function reloadCard(){
//     listCard.innerHTML = '';
//     let count = 0;
//     let totalPrice = 0;
//     listCards.forEach((value, key)=>{
//         totalPrice = totalPrice + value.price;
//         count = count + value.quantity;
//         if(value != null){
//             let newDiv = document.createElement('li');
//             newDiv.innerHTML = `
//                 <div><img src="image/${value.image}"/></div>
//                 <div>${value.name}</div>
//                 <div>${value.price.toLocaleString()}</div>
//                 <div>
//                     <button onclick="changeQuantity(${key}, ${value.quantity - 1})">-</button>
//                     <div class="count">${value.quantity}</div>
//                     <button onclick="changeQuantity(${key}, ${value.quantity + 1})">+</button>
//                 </div>`;
//                 listCard.appendChild(newDiv);
//         }
//     })
//     total.innerText = totalPrice.toLocaleString();
//     quantity.innerText = count;
// }
// function changeQuantity(key, quantity){
//     if(quantity == 0){
//         delete listCards[key];
//     }else{
//         listCards[key].quantity = quantity;
//         listCards[key].price = quantity * products[key].price;
//     }
//     reloadCard();
// }