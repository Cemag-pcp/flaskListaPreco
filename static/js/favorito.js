$(document).ready(function() {
    var $table = $('#table1');
    var $icon = $table.find('a#favorito i');
    
    // Check if any rows were previously marked as favorite
    var $favoriteRows = $table.find('tbody tr:has(a#favorito i.yellow)');
    if ($favoriteRows.length > 0) {
      $favoriteRows.find('a#favorito i').addClass('yellow');
      $table.find('tbody').prepend($favoriteRows.get().reverse());
    }
    
    // Click event handler for the 'a' element with id 'favorito'
    $table.on('click', 'a#favorito', function(event) {
      event.preventDefault(); // Prevent the default link behavior
      
      var $clickedRow = $(this).closest('tr'); // Get the clicked row
      var $clickedIcon = $(this).find('i'); // Get the clicked icon element
      
      // Toggle the color of the clicked icon
      $clickedIcon.toggleClass('yellow');
      
      // Move the clicked row based on its favorite status
      if ($clickedIcon.hasClass('yellow')) {
        // Move the row to the top of the table
        $table.find('tbody').prepend($clickedRow);
      } else {
        // Find the last favorite row and insert the clicked row after it
        var $lastFavoriteRow = $table.find('tbody tr:has(a#favorito i.yellow)').last();
        $clickedRow.insertAfter($lastFavoriteRow);
      }
    });
  });
  