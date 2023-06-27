 // Função para enviar os dados para o backend
 function sendData(obs) {
    // Faça uma requisição POST para o backend usando fetch
    fetch('/rota-do-backend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(obs)
    })
    .then(response => {
      // Verifique a resposta do backend
      if (response.ok) {
        alert('Itens enviados com sucesso!');
      } else {
        alert('Ocorreu um erro ao enviar os itens.');
      }
    })
    .catch(error => {
      alert('Ocorreu um erro ao enviar os itens: ' + error);
    });
  }

  // Obtenha o botão "Enviar"
  const enviarButtonObs = document.getElementById('btnEnviarObs');

  // Adicione um evento de clique ao botão "Enviar"
  enviarButtonObs.addEventListener('click', () => {
    const obs = [];

    // Obtenha todos os itens da lista
    const modalobs = document.querySelectorAll('.modal');

    // Percorra os itens e obtenha os dados
    modalobs.forEach(modalItem => {
      const nome = modalItem.getElementById('filtro-nome');
      const contato = modalItem.getElementById('filtro-contato');
      const pagamento = modalItem.getElementById('forma-pagamento')
      const observacao = modalItem.getElementById('observacao')

      const filtroNome = nome.textContent;
      const filtroContato = contato.textContent;
      const filtroPagamento = pagamento.textContent;
      const filtroObservacao = observacao.textContent;

      // Crie um objeto com os dados do item
      const ob = {
        filtroNome: filtroNome,
        filtroContato: filtroContato,
        filtroPagamento: filtroPagamento,
        filtroObservacao: filtroObservacao
      };

      // Adicione o obs à lista de itens
      obs.push(ob);
    });

    // Chame a função para enviar os dados para o backend
    sendData(obs);
  });